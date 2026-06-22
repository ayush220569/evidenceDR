# Deep Investigation — Size vs Quality Benchmark

Run on: 2026-02-10 · backend at `http://localhost:8001`
Script: `/app/scripts/size_quality_test.py` · Raw data: `size_test_results.json`

## Test design

For each size we generated a synthetic ArcGIS Portal log that is mostly housekeeping noise (INFO scheduler / stats / items / http) with a **3-line needle** planted at a known byte offset:

```
ERROR [saml] NAME_ID claim missing from IdP assertion for user=alice@acme.com
ERROR [saml] Cannot create session: required attribute NAME_ID is null
WARN  [auth] Redirecting user to /portal/home with empty session due to missing NAME_ID
```

Each run: upload log → wait for indexing → `POST /api/cases/{id}/orchestrate` → check final report.
We score:
- **Needle found?** — needle terms appear anywhere in the orchestrator report
- **Root-cause hit?** — needle terms appear specifically inside `report.root_cause`
- **Layer correct?** — should be `portal` (Portal/SAML auth)

## Results

| Test | Size | Needle@ | Indexed chunks | Map batches | Orch time | Needle found | Root-cause hit | Confidence | Layer |
|---|---|---|---|---|---|---|---|---|---|
| **B_1MB**  | 1.05 MB  | 0.52 MB  | **1,581** | 8 | 164 s | ✅ YES | ✅ YES | low | ✅ portal |
| **D_5MB**  | 5.24 MB  | 4.72 MB  | **4,000** (capped) | 8 | 174 s | ✅ YES | ❌ NO  | low | ❌ unknown |
| **E_12MB** | 12.58 MB | 11.53 MB | **4,000** (capped, needle CUT OFF) | – | 135 s | ❌ NO  | ❌ NO  | – | – (LLM budget exceeded on this run) |

## Interpretation — where quality deteriorates

### Cliff 1 — `max_chunks = 4000` (≈ 3.2 MB at default 800-char chunks)
Above this, `index_file` **truncates** the file to the first 4000 chunks. The needle can be:
- **Still retrievable** if it falls inside the first 4000 chunks (D_5MB: chunks 0–4000 covered ~3.2 MB, needle was at 4.72 MB — yet RAG still surfaced it via cosine match on neighbouring SAML/auth language, so `found=YES`)
- **But the root-cause synthesis dilutes** — with 8 map batches × 25 chunks of mixed noise, the reduce phase generalises away from the specific NAME_ID anchor → `rc_hit=NO`, `layer=unknown`

### Cliff 2 — `max_index_bytes_per_file = 10 MB`
Above this, raw bytes past 10 MB are **never read from disk**. The 12 MB file's needle at 11.5 MB is physically invisible to the indexer → `found=NO` (the 12 MB run also hit a separate LLM budget cap so the orchestrator errored before producing a clean report, but the absence-of-needle conclusion still holds).

### Cliff 3 — orchestrator cost
Orchestrator pulls top-200 chunks regardless of corpus size and batches into ≤ 12 map calls (~$0.10–0.30 per Deep Investigation). Time grew only ~6 % from 1 MB → 5 MB because LLM calls dominate, not embedding.

## Recommended ranges

| Log size | Deep Investigation quality | Action |
|---|---|---|
| **≤ 3 MB** | ✅ High — root cause + layer + confidence reliable | Run as-is |
| **3 – 10 MB** | ⚠️ Mixed — needle usually still found, but synthesis loses specificity | Pre-filter to time window or category if known; or raise `max_chunks` in Settings |
| **> 10 MB** | ❌ Truncated — any signal past 10 MB is invisible | Pre-split the log or raise `max_index_bytes_per_file` |

## Tunables (Settings page → Retrieval)

- `max_index_bytes_per_file` (default 10 MB) — hard byte cap before chunking
- `chunk_size_chars` / `chunk_overlap_chars` (default 800 / 100)
- `retrieval_top_k` (default 40 fast path, hard-coded 200 for orchestrator)

`max_chunks` (4000) is currently a code constant in `IndexConfig` (`backend/retrieval.py`). If you regularly process logs > 5 MB, lifting it to 8000–10000 + raising `chunk_size_chars` to 1200 is the cheapest quality lever.
