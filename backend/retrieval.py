"""Semantic retrieval layer for EvidencePilot AI.

- Embeddings: fastembed (BAAI/bge-small-en-v1.5) — runs locally, no network egress for log content
- Vector store: ChromaDB persistent client on local disk
- Single collection 'case_evidence' with case_id + file_id metadata for fast per-case scoping
- All ChromaDB / fastembed calls are pinned to ONE dedicated worker thread (sync_to_async helper below),
  because chromadb's PersistentClient registry is not safe to share across arbitrary threads.
"""
import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from fastembed import TextEmbedding


CHROMA_DIR = Path(os.environ.get("CHROMA_DIR", "/app/backend/chroma_data"))
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

EMBED_MODEL_NAME = os.environ.get("EVIDENCEPILOT_EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# Dedicated single-thread executor for ALL chromadb / fastembed work.
# Pinning to one worker thread sidesteps chromadb's non-thread-safe client registry
# while keeping the FastAPI event loop free for concurrent API calls.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ep-retrieval")


async def run_sync(fn, *args, **kwargs):
    """Run a sync function in the dedicated retrieval worker thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, lambda: fn(*args, **kwargs))


@dataclass
class IndexConfig:
    """Tuning parameters for indexing a single file into the vector store."""
    chunk_chars: int = 800
    overlap_chars: int = 100
    max_chunks: int = 10000


# Severity tokens used by the lexical branch of hybrid retrieval.
# chromadb's where_document $contains is case-sensitive substring, so we include the
# common casings actually seen in ArcGIS / IIS / Portal / Pro / Java logs. Keep this
# tight — over-broad terms ("error", "warn") would match item names, paths, etc.
SEVERITY_TERMS: List[str] = [
    "ERROR", "FATAL", "CRITICAL",
    "WARN ", "WARNING",
    "Exception", "EXCEPTION",
    "Traceback", "stack trace",
    "ACCESS_DENIED", "AccessDenied", "Forbidden",
    "FAILED", " FAIL ",
    "timeout", "Timeout", "TIMEOUT",
    "denied",
]


class _Singletons:
    """Lazy singletons for ChromaDB client, collection, and the embedder.

    Wrapped in a class so static analyzers see definite assignment for every attribute,
    and so we avoid module-level `global` declarations.
    """
    client: Optional[chromadb.api.client.Client] = None
    collection = None
    embedder: Optional[TextEmbedding] = None


def _client_get():
    if _Singletons.client is None:
        _Singletons.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
    return _Singletons.client


def _collection_get():
    """Lazy-create the 'case_evidence' collection (cosine similarity)."""
    if _Singletons.collection is None:
        _Singletons.collection = _client_get().get_or_create_collection(
            name="case_evidence",
            metadata={"hnsw:space": "cosine"},
        )
    return _Singletons.collection


def _embedder_get() -> TextEmbedding:
    """Lazy-load fastembed model (first call downloads ~80MB ONNX model)."""
    if _Singletons.embedder is None:
        _Singletons.embedder = TextEmbedding(model_name=EMBED_MODEL_NAME)
    return _Singletons.embedder


def embed(texts: List[str]) -> List[List[float]]:
    """Return list of plain-python float vectors (ChromaDB 1.5 strict-checks for builtin floats, not np.float32)."""
    if not texts:
        return []
    return [[float(x) for x in v] for v in _embedder_get().embed(texts)]


# -------- chunking --------
_LINE_BREAK_RE = re.compile(r"\n")


def chunk_text(text: str, chunk_chars: int = 800, overlap_chars: int = 100) -> List[str]:
    """Char-window chunking with paragraph awareness. Cheap, fast, and works well for logs.

    Splits on paragraph/line boundaries when possible so we don't cut mid-stacktrace.
    """
    if not text or not text.strip():
        return []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks: List[str] = []
    i, n = 0, len(text)
    while i < n:
        end = min(i + chunk_chars, n)
        # try to break on a newline within last 25% of chunk window for cleaner cuts
        if end < n:
            window_start = i + int(chunk_chars * 0.75)
            nl = text.rfind("\n", window_start, end)
            if nl > i + 200:
                end = nl
        piece = text[i:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        i = max(end - overlap_chars, i + 1)
    return chunks


# -------- index / retrieve --------
def index_file(case_id: str, file_id: str, file_name: str, layer: str, text: str,
               config: Optional[IndexConfig] = None) -> int:
    """Embed and persist chunks for a single uploaded file. Idempotent: clears existing entries for (case_id, file_id) first."""
    cfg = config or IndexConfig()
    # remove existing chunks for this file
    clear_file(case_id, file_id)

    chunks = chunk_text(text, chunk_chars=cfg.chunk_chars, overlap_chars=cfg.overlap_chars)
    if not chunks:
        return 0
    if len(chunks) > cfg.max_chunks:
        chunks = chunks[:cfg.max_chunks]

    ids = [f"{case_id}:{file_id}:{i}" for i in range(len(chunks))]
    metadatas = [
        {"case_id": case_id, "file_id": file_id, "file_name": file_name, "layer": layer or "unknown", "chunk_index": i}
        for i in range(len(chunks))
    ]
    col = _collection_get()
    # Embed + upsert in batches: previously we embedded the whole file at once which spiked
    # memory (large logs → 100+ MB of float vectors held simultaneously) and made the chroma
    # thread look hung. Batching keeps RSS bounded and lets the indexed_chunks counter
    # grow during the run so the UI / benchmark sees progress.
    B = 256
    total_chunks = len(chunks)
    for s in range(0, total_chunks, B):
        batch_chunks = chunks[s:s + B]
        batch_embs = embed(batch_chunks)
        col.upsert(
            ids=ids[s:s + B],
            documents=batch_chunks,
            embeddings=batch_embs,
            metadatas=metadatas[s:s + B],
        )
    return total_chunks


def retrieve(case_id: str, query: str, top_k: int = 40) -> List[dict]:
    """Hybrid retrieval: semantic top-K fused with a severity-filtered ('lexical') top-K.

    Why hybrid: in homogeneous noisy logs (housekeeping/INFO dominated), a tiny number of
    ERROR/WARN/FATAL chunks are structurally similar to the noise around them, so a pure
    semantic search ranks them near the noise floor. We separately query chromadb for chunks
    that *contain* severity keywords and merge the two ranked lists via Reciprocal Rank Fusion
    (RRF), which gives a high-recall result without needing a re-rank model.

    The fused result is the same shape the caller already expects; an extra `source` field
    ('semantic' | 'lexical' | 'hybrid') is set so the UI can show why a chunk surfaced.
    """
    if not query or not query.strip():
        return []
    col = _collection_get()
    # count chunks in case first to avoid k > n_results errors
    try:
        existing = col.get(where={"case_id": case_id}, include=[])
        n = len(existing.get("ids", []))
    except Exception:
        n = 0
    if n == 0:
        return []
    k_sem = min(top_k, n)
    q_emb = embed([query])

    # ---- Semantic branch ----
    res_sem = col.query(
        query_embeddings=q_emb,
        n_results=k_sem,
        where={"case_id": case_id},
        include=["documents", "metadatas", "distances"],
    )
    sem_ids = (res_sem.get("ids") or [[]])[0]
    sem_docs = (res_sem.get("documents") or [[]])[0]
    sem_metas = (res_sem.get("metadatas") or [[]])[0]
    sem_dists = (res_sem.get("distances") or [[]])[0]

    # ---- Lexical branch (severity-filtered) ----
    # Use chromadb's where_document $contains with an $or across severity tokens.
    # If the case has zero severity-bearing chunks this returns an empty result set.
    sev_filter = {"$or": [{"$contains": term} for term in SEVERITY_TERMS]}
    lex_ids: List[str] = []
    lex_docs: List[str] = []
    lex_metas: List[dict] = []
    lex_dists: List[float] = []
    try:
        # Probe how many severity-bearing chunks exist before asking for k of them
        lex_existing = col.get(
            where={"case_id": case_id},
            where_document=sev_filter,
            include=[],
        )
        n_lex = len(lex_existing.get("ids", []))
        if n_lex > 0:
            k_lex = min(top_k, n_lex)
            res_lex = col.query(
                query_embeddings=q_emb,
                n_results=k_lex,
                where={"case_id": case_id},
                where_document=sev_filter,
                include=["documents", "metadatas", "distances"],
            )
            lex_ids = (res_lex.get("ids") or [[]])[0]
            lex_docs = (res_lex.get("documents") or [[]])[0]
            lex_metas = (res_lex.get("metadatas") or [[]])[0]
            lex_dists = (res_lex.get("distances") or [[]])[0]
    except Exception:
        # chromadb $or on where_document may not be supported on older versions;
        # silently fall back to pure semantic in that case.
        pass

    # ---- Reciprocal Rank Fusion (k=60 is the canonical constant from the RRF paper) ----
    RRF_K = 60
    fused: Dict[str, dict] = {}

    def _add(ids: list, docs: list, metas: list, dists: list, source: str):
        for rank, _id in enumerate(ids):
            if rank >= len(docs):
                break
            slot = fused.get(_id)
            score_contrib = 1.0 / (RRF_K + rank + 1)
            if slot is None:
                slot = {
                    "_id": _id, "rrf": 0.0, "sources": set(),
                    "doc": docs[rank], "meta": metas[rank] if rank < len(metas) else {},
                    "dist": dists[rank] if rank < len(dists) else None,
                }
                fused[_id] = slot
            slot["rrf"] += score_contrib
            slot["sources"].add(source)
            # prefer the smallest cosine distance seen for this id (used for display score)
            if dists and rank < len(dists):
                cur = slot.get("dist")
                if cur is None or dists[rank] < cur:
                    slot["dist"] = dists[rank]

    _add(sem_ids, sem_docs, sem_metas, sem_dists, "semantic")
    _add(lex_ids, lex_docs, lex_metas, lex_dists, "lexical")

    # Sort by fused RRF score, take top_k
    ranked = sorted(fused.values(), key=lambda s: s["rrf"], reverse=True)[:top_k]

    out: List[dict] = []
    for s in ranked:
        meta = s["meta"] or {}
        sources = sorted(s["sources"])
        out.append({
            "text": s["doc"],
            "file_name": meta.get("file_name"),
            "file_id": meta.get("file_id"),
            "layer": meta.get("layer"),
            "chunk_index": meta.get("chunk_index"),
            "distance": float(s["dist"]) if s.get("dist") is not None else None,
            "score": round(max(0.0, 1.0 - float(s["dist"])), 4) if s.get("dist") is not None else None,
            "rrf_score": round(s["rrf"], 5),
            "source": "hybrid" if len(sources) > 1 else sources[0],
        })
    return out


def clear_file(case_id: str, file_id: str) -> int:
    col = _collection_get()
    try:
        existing = col.get(where={"$and": [{"case_id": case_id}, {"file_id": file_id}]}, include=[])
        ids = existing.get("ids") or []
        if ids:
            col.delete(ids=ids)
        return len(ids)
    except Exception:
        return 0


def clear_case(case_id: str) -> int:
    col = _collection_get()
    try:
        existing = col.get(where={"case_id": case_id}, include=[])
        ids = existing.get("ids") or []
        if ids:
            col.delete(ids=ids)
        return len(ids)
    except Exception:
        return 0


def count_case(case_id: str) -> int:
    try:
        col = _collection_get()
        existing = col.get(where={"case_id": case_id}, include=[])
        return len(existing.get("ids") or [])
    except Exception:
        return 0


def build_query(case: dict) -> str:
    """Compose a retrieval query from case context, symptom clues, and logic answers."""
    ctx = case.get("context", {}) or {}
    parts = [
        case.get("title", ""),
        case.get("category_name", ""),
        ctx.get("summary", ""),
        ctx.get("repro_steps", ""),
        ctx.get("recent_changes", ""),
        ctx.get("topology", ""),
        " ".join(case.get("symptom_clues") or []),
        " ".join([f"{a.get('question','')} {a.get('answer_label','')}" for a in (case.get('logic_answers') or [])]),
    ]
    # Add domain anchors so retrieval surfaces relevant log patterns even when context is thin
    parts.append("ERROR Exception WARN CRITICAL FATAL stack trace ACCESS_DENIED 401 403 404 500 502 timeout")
    return "\n".join([p for p in parts if p]).strip()
