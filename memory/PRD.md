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

## Backlog / future
- P1: Auth (AD / SSO / IIS auth front)
- P1: Scheduled retention purge job
- P2: Richer EVTX & dump parsing
- P2: Case sharing / templates / multi-tenant
- P2: Charts on dashboard (Recharts)
- P2: PDF export
