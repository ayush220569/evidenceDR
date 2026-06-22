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

## Upgraded in v1.2 (2026-02-11) — Deep Investigation size benchmark
- Made background indexing fully non-blocking: `extract_text` now goes through `asyncio.to_thread` before the chromadb single-thread worker, so concurrent API calls stay responsive even while embedding multi-MB files.
- Indexed-chunk count is now persisted back to the case file metadata once indexing completes (`files.indexed=true`, `files.indexed_chunks=N`).
- Ran `/app/scripts/size_quality_test.py` benchmark over 1 / 5 / 12 MB synthetic SAML-incident logs to characterise the quality cliffs of the orchestrator pipeline. Full write-up: `/app/scripts/SIZE_QUALITY_REPORT.md`. Headline:
  - ≤ 3 MB → high quality: needle found, root cause + layer correct (B_1MB: 1,581 chunks, 164 s, conf=low, layer=portal)
  - 3 – 10 MB → degrades: needle still retrieved but synthesis dilutes (D_5MB: 4,000 capped chunks, found=YES but rc_hit=NO, layer=unknown)
  - > 10 MB → hard byte cap (`max_index_bytes_per_file`) cuts content past 10 MB out entirely
  - Knobs: lift `IndexConfig.max_chunks` from 4000 → 8000+ in `backend/retrieval.py` and raise `chunk_size_chars` to 1200 in Settings for big-log fidelity.

## Backlog / future
- P1: PDF export (currently Markdown / HTML / JSON only)
- P1: Auth (AD / SSO / IIS auth front)
- P1: Scheduled retention purge job
- P1: Expose `max_chunks` as a Settings field (currently a code constant)
- P2: Richer EVTX & dump parsing
- P2: Case sharing / templates / multi-tenant
- P2: Charts on dashboard (Recharts)
- P2: Pre-filter large logs by time window before indexing
