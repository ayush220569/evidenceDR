"""Semantic retrieval layer for EvidencePilot AI.

- Embeddings: fastembed (BAAI/bge-small-en-v1.5) — runs locally, no network egress for log content
- Vector store: ChromaDB persistent client on local disk
- Single collection 'case_evidence' with case_id + file_id metadata for fast per-case scoping
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from fastembed import TextEmbedding


CHROMA_DIR = Path(os.environ.get("CHROMA_DIR", "/app/backend/chroma_data"))
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

EMBED_MODEL_NAME = os.environ.get("EVIDENCEPILOT_EMBED_MODEL", "BAAI/bge-small-en-v1.5")


@dataclass
class IndexConfig:
    """Tuning parameters for indexing a single file into the vector store."""
    chunk_chars: int = 800
    overlap_chars: int = 100
    max_chunks: int = 4000


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
    embeddings = embed(chunks)
    col = _collection_get()
    # add in batches to avoid huge payloads
    B = 256
    for s in range(0, len(chunks), B):
        col.upsert(
            ids=ids[s:s + B],
            documents=chunks[s:s + B],
            embeddings=embeddings[s:s + B],
            metadatas=metadatas[s:s + B],
        )
    return len(chunks)


def retrieve(case_id: str, query: str, top_k: int = 40) -> List[dict]:
    """Return top-K chunks for a case, ranked by cosine similarity."""
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
    k = min(top_k, n)
    q_emb = embed([query])
    res = col.query(
        query_embeddings=q_emb,
        n_results=k,
        where={"case_id": case_id},
        include=["documents", "metadatas", "distances"],
    )
    out: List[dict] = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append({
            "text": doc,
            "file_name": meta.get("file_name"),
            "file_id": meta.get("file_id"),
            "layer": meta.get("layer"),
            "chunk_index": meta.get("chunk_index"),
            "distance": float(dist),
            "score": round(max(0.0, 1.0 - float(dist)), 4),  # cosine → similarity 0..1
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
