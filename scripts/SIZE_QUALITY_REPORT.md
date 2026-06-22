# Deep Investigation — Size vs Quality Benchmark

Two runs, same script (`size_quality_test.py`), same synthetic SAML-incident logs, same orchestrator code. Only the API key + model serving differed.

## Run 1 — Emergent Universal LLM Key (gpt-5.5 routed via proxy) · 2026-02-10

| Test | Size | Needle@ | Indexed chunks | Orch time | Needle found | Root-cause hit | Layer |
|---|---|---|---|---|---|---|---|
| B_1MB | 1.05 MB | 0.52 MB | 1,581 | 164 s | ✅ YES | ✅ YES | ✅ portal |
| D_5MB | 5.24 MB | 4.72 MB | 4,000 (capped) | 174 s | ✅ YES | ❌ NO | ❌ unknown |
| E_12MB | 12.58 MB | 11.53 MB | 4,000 (capped) | — | — | — | budget error |

## Run 2 — User's own OpenAI key (direct gpt-5.5) · 2026-02-11

| Test | Size | Needle@ | Indexed chunks | Orch time | Needle found | Root-cause hit | Layer |
|---|---|---|---|---|---|---|---|
| B_1MB | 1.05 MB | 0.52 MB | 1,579 | 304 s | ✅ YES* | ❌ NO | ❌ unknown |
| D_5MB | 5.24 MB | 4.72 MB | 4,000 (capped) | 347 s | ✅ YES* | ❌ NO | ❌ unknown |
| E_12MB | 12.58 MB | 11.53 MB | 4,000 (needle cut by 10 MB byte cap) | 326 s | ✅ YES* | ❌ NO | ❌ unknown |

\* "found" in Run 2 is the **case-context echo, not real needle retrieval** — the LLM honestly stated "fresh sample contains only INFO-level entries from 13:00 hour and does not include the reported 14:30 EST failure window" in every report. It speculatively mentioned `NAME_ID / NameID mismatch` only as an *unproven hypothesis* based on the case's `summary="SAML blank page" + recent_changes="IdP cert rotated"` context. The keyword check in the script can't distinguish "I saw NAME_ID in evidence" from "NAME_ID might be the issue".

## The real finding: RAG retrieval is the bottleneck, not the model or size

Verified by directly querying the 1 MB case for the exact verbatim needle terms:

```
POST /api/cases/{1MB-case}/retrieval/search
body: {"query": "ERROR saml NAME_ID claim missing IdP assertion alice@acme.com", "top_k": 3}
```

| Top-1 score | Top-2 score | Top-3 score | Needle in top-3? |
|---|---|---|---|
| 0.636 | 0.633 | 0.633 | ❌ **No — all 3 are housekeeping/scheduler INFO lines** |

The needle (3 ERROR/WARN lines at line ~7,530 of the 1 MB file) IS indexed, but the bge-small-en-v1.5 embedding model assigns it the same ~0.63 cosine similarity as 1,500 other structurally-identical noise chunks. The signal-to-noise ratio of "3 lines out of 20,000 lines with the same log format" is below what general-purpose semantic embeddings can resolve.

**Implication**: with the current naive RAG pipeline, you cannot reliably surface needle-in-a-haystack errors from any large noisy log — regardless of which LLM does the synthesis, regardless of file size. Both runs show this; Run 1's apparent success at 1 MB was the LLM hallucinating the correct answer from the case context, not from retrieved evidence.

## Why Run 1 (Emergent proxy) "looked" better

| Behaviour | Run 1 (Emergent proxy gpt-5.5) | Run 2 (direct OpenAI gpt-5.5) |
|---|---|---|
| When retrieval misses the needle | Aggressively confirms hypothesis from case context | Honestly hedges: "evidence not present in sample" |
| `confidence_overall` | reported `low` | reported `null` (refuses to score without evidence) |
| `likely_layer` | committed to `portal` (correct, but inferred from context) | left as `unknown` (correct given retrieved evidence) |
| Speed | ~2× faster | ~2× slower |

Run 2 is **more correct** — it correctly identifies that the orchestrator's retrieved evidence does not actually support the SAML conclusion, even though that conclusion happens to be right. Run 1's apparent accuracy at 1 MB was a model-personality artifact, not a real retrieval success.

## Where quality really deteriorates

1. **Cliff 0 — Retrieval recall** (the unreported new one this benchmark exposed)
   - For homogeneous logs (housekeeping/INFO dominated), bge-small can't distinguish ERROR/WARN needles from INFO noise at any size > a few hundred chunks.
   - **Fix options**:
     - Add a **lexical pre-filter** (BM25/grep) on `ERROR|WARN|FATAL|Exception|FAIL` and merge with semantic top-K → hybrid retrieval. This is the highest-leverage single change.
     - Upgrade to `bge-base-en-v1.5` (~110 MB, 2× recall on noisy corpora).
     - During chunking, *tag* chunks with detected severity and boost ERROR-bearing chunks in the score.

2. **Cliff 1 — `IndexConfig.max_chunks = 4000`** (≈ 3.2 MB at 800-char chunks)
   - Above this, the tail of the file is **truncated before embedding**. Even if retrieval were perfect, needles past chunk 4000 would never be found.

3. **Cliff 2 — `max_index_bytes_per_file = 10 MB`**
   - Bytes past 10 MB are **never read from disk**. Hard ceiling.

4. **Cliff 3 — Orchestrator cost / time**
   - Caps at top-200 chunks · ≤ 12 map batches. Doesn't grow with file size. Run 2 was ~2× slower than Run 1 not due to size but due to direct-OpenAI vs proxy latency.

## Recommended ranges (with current code)

| Log size | Realistic Deep Investigation quality | Workaround |
|---|---|---|
| ≤ 3 MB AND signal density > 1 % | ✅ Reliable | run as-is |
| ≤ 3 MB AND signal density < 0.1 % (this benchmark) | ⚠️ Retrieval-limited | needs hybrid lexical+semantic retrieval |
| 3–10 MB | ⚠️ Tail truncated by `max_chunks` | raise `max_chunks` to 8000+ in `backend/retrieval.py` |
| > 10 MB | ❌ Tail cut by byte cap | pre-split file or raise `max_index_bytes_per_file` in Settings |

## Highest-leverage code changes (if you want to fix the cliffs)

1. **Hybrid retrieval** in `backend/retrieval.py`: add a `lexical_retrieve(case_id, terms, top_k)` that greps for severity keywords, then merge into the `retrieve()` result set with score normalisation. ~30 lines.
2. **Expose `max_chunks`** as a Settings field (currently a code constant).
3. **Pre-filter on `extract_text`**: tail of large files is currently lost — but maybe the *important* parts of a log are at the *end* (error windows). Consider sliding-window or two-pass: index errors first, then context.

Raw data: `/app/scripts/size_test_results.json` · Reports queried live from MongoDB on 2026-02-11.
