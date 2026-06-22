# EvidencePilot AI — PRD

## Original problem statement
Build a production-oriented full-stack web app for ArcGIS / Enterprise / Pro support log triage and evidence collection guidance. Must help support engineers collect right evidence on first attempt, analyze logs with AI (two providers side-by-side), and guide troubleshooting through a gamified decision tree. Dark cockpit theme, gamified, professional. Windows VM hosting target.

## Architecture
- **Frontend**: React 19 + Tailwind + shadcn/ui + @phosphor-icons/react + framer-motion
- **Backend**: FastAPI + Motor (async MongoDB) + emergentintegrations (LlmChat)
- **DB**: MongoDB collections: `cases`, `settings`
- **Storage**: filesystem at `UPLOAD_DIR=/app/backend/uploads/<case_id>/`
- **AI**: Provider A = OpenAI gpt-5.2; Provider B = Anthropic claude-sonnet-4-5-20250929 (labeled "Microsoft / Copilot-style"), both via Emergent Universal LLM Key, override-able per provider in Settings.

## User personas
- Tier-1 / Tier-2 ArcGIS support engineer
- Technical analyst / SME
- Escalation/triage manager

## Core requirements (static)
- 10 issue categories with rules: AGOL admin, Auth/SAML, Web tier, Portal ops, Server/services, Data Store, WebGISDR, Licensing, Pro crash, Pro hang
- Drag-and-drop file uploader (.log/.txt/.json/.xml/.csv/.har/.zip/.dmp/.evtx/images/pdf), zip safe-extract
- Auto layer detection (Browser / Web tier / Portal / Server / Data Store / Pro client / OS)
- Gamified logic tree per category
- Dual-AI analysis run in parallel with async background job + polling
- Evidence completeness scoring (context fields × layer coverage)
- First-pass readiness meter (low/medium/high)
- Export Markdown / JSON / printable HTML
- Editable escalation contact (default `corp.support.help@esri.ca`)

## Implemented in v1.0 (2026-02-10)
- Backend: 23 REST endpoints (categories, logic-tree, cases CRUD, file upload+preview+layer-update+zip-extract, logic save, score, async analyze + status, settings, dashboard stats, exports)
- Frontend: 7 routes — Dashboard, New Analysis (3-step wizard), Cases List, Case Workspace (5 tabs), Guidance Library, Settings, Help
- Async AI analysis with background task + polling (avoids 60s ingress cap)
- README with full Windows VM deployment guide (NSSM, IIS reverse proxy)
- 22/23 backend tests + 100% frontend smoke tests passed (testing_agent_v3 iter 1)

## Upgraded in v1.1 (2026-02-10) — RAG / semantic retrieval
- Replaced naive truncation pipeline (8KB/file, 30KB total) with **full RAG**:
  - Embeddings: **fastembed** (BAAI/bge-small-en-v1.5, local ONNX, no torch) — runs entirely inside the VM, no log content sent over the network for embedding
  - Vector store: **ChromaDB PersistentClient** at `/app/backend/chroma_data` — survives backend restarts, single `case_evidence` collection scoped by `case_id` + `file_id` metadata
  - Chunking: character-window (default 800 chars, 100 overlap) with paragraph-boundary preference; per-file cap 10 MB
- New endpoints: `GET/POST /api/cases/{id}/retrieval/{stats,search}`, `POST /api/cases/{id}/files/{fid}/reindex`
- Wired into upload pipeline (BackgroundTasks) and zip extraction; file/case delete now purges vectors
- `_run_analysis_job` builds a query from case context + symptom clues + logic answers, retrieves top-K (default 40), and feeds chunks to both providers; persists `ai_results.retrieval` metadata
- Frontend: new **Retrieved Evidence (RAG)** panel in Case Workspace → AI Comparison tab; Settings page exposes top-K / chunk size / overlap / max index bytes
- Tested: 40/42 backend tests + 100% frontend (testing_agent_v3 iter 2). Semantic scoring verified — relevant SAML chunks scored 0.738 vs irrelevant noise 0.526.

## Upgraded in v1.3 (2026-02-11) — Hybrid retrieval (lexical + semantic, RRF-fused)
Identified during the size-vs-quality benchmark: pure semantic retrieval (`bge-small`) cannot surface ERROR/WARN needles in noisy INFO-dominated logs. Verified by directly querying a 1 MB case for verbatim needle terms — top-3 results were all housekeeping INFO (scores 0.63), needle absent from top-200.

Implemented hybrid retrieval in `backend/retrieval.py`:
- New `SEVERITY_TERMS` constant: `ERROR`, `FATAL`, `CRITICAL`, `WARN`, `WARNING`, `Exception`, `Traceback`, `ACCESS_DENIED`, `Forbidden`, `FAILED`, `timeout`, `denied`, etc.
- `retrieve()` now runs two parallel chromadb queries: (1) pure semantic top-K, (2) semantic top-K *restricted* to chunks containing severity tokens via `where_document.$or.$contains`.
- Both result lists are merged via **Reciprocal Rank Fusion** (RRF, k=60) — gold-standard fusion that needs no calibration.
- Each result is tagged with `source ∈ {semantic, lexical, hybrid}` so the UI can show why a chunk surfaced (orange = lexical, green = hybrid).
- Graceful fallback: if chromadb's `$or` on `where_document` isn't supported on the deployed version, falls back to pure semantic without error.
- Clean logs (no severity tokens) → 100 % semantic results, no regression on happy-path corpora.

End-to-end validation on the 1 MB SAML-blank-page case (same case that returned `rc_hit=NO, layer=unknown` before):

| Metric | Semantic-only (before) | Hybrid (after) |
|---|---|---|
| Needle rank in top-200 | not present | rank 1 (lexical) |
| Best needle score | – | 0.80 (vs 0.63 noise floor) |
| Orchestrator `root_cause.primary_hypothesis` | "Root cause not confirmed from supplied evidence" | "The SAML assertion did not include the required NAME_ID claim, so Portal could not create a session…" (cites verbatim ERROR/WARN lines) |
| `likely_layer` | unknown | portal ✅ |

Regression test added at `backend/tests/test_hybrid_retrieval.py`.

## Backlog / future
- P1: PDF export (currently Markdown / HTML / JSON only)
- P1: Auth (AD / SSO / IIS auth front)
- P1: Expose `max_chunks` as a Settings field (currently a code constant)
- P1: Pre-flight upload warning when file size would exceed `max_chunks` / `max_index_bytes` caps
- P2: Tail-first or sliding-window indexing for >10 MB logs (errors often live at the tail)
- P2: Upgrade to `bge-base-en-v1.5` for ~2× recall on technical text
- P2: Richer EVTX & dump parsing
- P2: Case sharing / templates / multi-tenant
- P2: Charts on dashboard (Recharts)
- P2: Scheduled retention purge job
