# EvidencePilot AI

> **Smarter first-pass evidence collection and log triage for ArcGIS support.**

A production-oriented full-stack web app that helps support engineers and technical analysts collect the *right* evidence on the **first attempt**, analyze uploaded logs with **two AI providers side-by-side**, and guides troubleshooting through a **gamified decision tree** based on issue category and clues.

---

## A. Project Overview

**Who is this for?**
Support engineers, technical analysts, and SMEs working ArcGIS Online / ArcGIS Enterprise / ArcGIS Pro support cases who are tired of chasing customers for missing logs.

**Key features**

* 10 pre-defined issue categories with category-specific evidence rules
* Drag-and-drop multi-file uploader (`.log .txt .json .xml .csv .har .zip .dmp .evtx .png .pdf`)
* Automatic layer detection (Browser / Web tier / Portal / Server / Data Store / Pro client / OS)
* Safe zip extraction with path-traversal protection
* **Semantic retrieval (RAG) over uploaded files** — local fastembed (BAAI/bge-small-en-v1.5, ONNX, no torch) + ChromaDB persistent vector store. Embeddings run inside your VM (no log data egress) and survive across cases/restarts.
* Gamified logic tree (per-category questions; mission-flow UX)
* **Dual-AI analysis** — runs Provider A & Provider B in parallel and shows a diff, fed by retrieved chunks
* Evidence completeness scoring (context fields × layer coverage)
* First-pass readiness meter + escalation checklist
* Export to **Markdown / JSON / printable HTML**
* Configurable retention, max upload size, escalation contact, and RAG tuning (top-k / chunk size / overlap / per-file index cap)

**Architecture**

```
[ React 19 + Tailwind + shadcn/ui ]   ← frontend (port 3000)
                |
                ▼  REACT_APP_BACKEND_URL/api
[ FastAPI + Motor (async MongoDB) ]   ← backend  (port 8001)
        |               |              |
        ▼               ▼              ▼
  [ MongoDB ]   [ /backend/uploads/<case_id>/ ]   [ ChromaDB persistent /backend/chroma_data/ ]
                                                  + fastembed (local ONNX, ~80MB on first use)
```

Both AI providers go through the **OpenAI AI provider abstraction** (`backend/ai_providers.py`). By default both providers share the **OpenAI Universal LLM Key**; per-provider override keys can be set in **Settings**. The prompt that goes to each provider contains only the **top-K semantically-relevant chunks** retrieved from ChromaDB — never the raw log bytes.

---

## B. Prerequisites

| Component | Required version |
|---|---|
| Windows Server | 2019 or 2022 |
| Python | 3.11+ |
| Node.js | 20.x LTS |
| Yarn | 1.22+ (project uses Yarn classic) |
| MongoDB | 6.x or 7.x |
| (optional) IIS | for reverse proxy / TLS termination |
| Disk | 5 GB free for app + uploads |

API keys: an **OpenAI LLM Key** is provided out-of-the-box. Optional: your own OpenAI key and/or Azure OpenAI / Microsoft endpoint key — configure in **Settings**.

---

## C. Installation (development)

```bash
# 1) Clone
git clone <repo> evidencepilot && cd evidencepilot

# 2) Backend
cd backend
pip install -r requirements.txt
# emergentintegrations ships from Emergent's private package index — install it separately:
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
# Edit backend/.env (see .env.example below)

# 3) Frontend
cd ../frontend
yarn install
# Edit frontend/.env (see below)

# 4) Run (dev)
# Terminal 1
cd backend && uvicorn server:app --host 0.0.0.0 --port 8001 --reload
# Terminal 2
cd frontend && yarn start    # serves on :3000, proxies via REACT_APP_BACKEND_URL
```

### `backend/.env.example`

```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="evidencepilot"
CORS_ORIGINS="*"
EMERGENT_LLM_KEY="sk-emergent-..."
UPLOAD_DIR="/app/backend/uploads"
CHROMA_DIR="/app/backend/chroma_data"
# optional override of embedding model (fastembed-compatible)
# EVIDENCEPILOT_EMBED_MODEL="BAAI/bge-small-en-v1.5"
```

### `frontend/.env.example`

```
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## D. Windows VM deployment (production)

1. **Install runtimes**
   - Python 3.11 (add to PATH)
   - Node 20 LTS + Yarn (`npm install -g yarn`)
   - MongoDB 7 Community as a Windows service

2. **Folder layout**
   ```
   C:\evidencepilot\
       backend\
       frontend\
       uploads\        ← grant write to the service account
   ```

3. **Backend service via NSSM**
   ```
   nssm install EvidencePilotBackend "C:\Python311\python.exe"
   nssm set EvidencePilotBackend AppParameters "-m uvicorn server:app --host 0.0.0.0 --port 8001"
   nssm set EvidencePilotBackend AppDirectory "C:\evidencepilot\backend"
   nssm set EvidencePilotBackend AppEnvironmentExtra ^
       MONGO_URL=mongodb://localhost:27017 ^
       DB_NAME=evidencepilot ^
       UPLOAD_DIR=C:\evidencepilot\uploads ^
       EMERGENT_LLM_KEY=sk-emergent-...
   nssm start EvidencePilotBackend
   ```

4. **Frontend build & service**
   ```
   cd C:\evidencepilot\frontend
   yarn install && yarn build
   npm install -g serve
   nssm install EvidencePilotFrontend "C:\Program Files\nodejs\node.exe"
   nssm set EvidencePilotFrontend AppParameters "C:\Users\...\AppData\Roaming\npm\node_modules\serve\bin\serve.js -s build -l 3000"
   nssm start EvidencePilotFrontend
   ```

5. **IIS reverse proxy (optional but recommended)**
   - Install URL Rewrite + Application Request Routing
   - In `web.config` route `/api/*` → `http://localhost:8001/api/*` and everything else → `http://localhost:3000/$&`

6. **Firewall**
   - Inbound 80/443 (or 3000 if not fronted by IIS)
   - Allow loopback for backend port

7. **Backup**
   - `mongodump --db evidencepilot --out backups/$(Get-Date -F yyyyMMdd)`
   - Sync `C:\evidencepilot\uploads\` to your backup target

---

## E. Configuration

In-app **Settings**:

| Setting | Default | Notes |
|---|---|---|
| Provider A | OpenAI / `gpt-5.5` | Override key field accepts any OpenAI-compatible key |
| Provider B | Anthropic / `claude-sonnet-4-5-20250929` | Labeled "Microsoft / Copilot-style" — change `provider/model` to point at Azure OpenAI or other compatible endpoints |
| Retention (days) | 30 | Used for scheduled cleanup (manual today) |
| Max upload (MB) | 512 | Per-file cap |
| Escalation contact | `corp.support.help@esri.ca` | Editable per deployment |
| Retrieval top-K | 40 | Chunks fed to each LLM per analysis run |
| Chunk size (chars) | 800 | Length of each indexed text chunk |
| Chunk overlap (chars) | 100 | Overlap between consecutive chunks |
| Max index bytes / file | 10 MB | Per-file cap when indexing into ChromaDB |

---

## F. How to use

1. **Dashboard** → click **New Analysis**
2. Pick **category** & confirm **symptom clues**
3. Fill the **context** form (timestamps + timezone, URLs, versions, topology, recent changes, repro steps)
4. Inside the **Case Workspace**:
   - Drop log files (auto layer-detection, drag re-classify)
   - Open the **Logic Tree** tab and answer the guided questions
   - Click **Run dual-AI** for side-by-side analysis
   - Review **Gaps & Next Steps** + **Escalation Checklist**
   - Open **Export** tab → download Markdown / JSON / HTML

---

## G. Limitations

* AI analysis is **advisory**, not authoritative.
* Binary formats (`.dmp`, `.evtx`) are not deeply parsed in the MVP — use WinDbg / `wevtutil` externally.
* Model quality depends on uploaded evidence quality.
* "Microsoft / Copilot" endpoints vary by org — the Provider B adapter is configurable; wire to Azure OpenAI by overriding key + model in Settings.
* Large log bundles are chunked at ~30 KB total per analysis run; for huge bundles, split per-layer.
* Local admin auth is intentionally lightweight — front the app with IIS auth / AD / SSO for production.

---

## H. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App won't start | Port 8001 in use | `Get-NetTCPConnection -LocalPort 8001` |
| AI returns "No API key" | EMERGENT_LLM_KEY missing | Set env var or override in Settings |
| Provider timeout | Model under load | Re-run; lower file excerpts |
| Large file fails | Exceeds `max_upload_mb` | Raise cap in Settings |
| Zip extraction blocked | Path traversal attempted | This is correct — file is malicious |
| Mongo lock | Service down | `Get-Service MongoDB` → restart |

---

## I. Future enhancements

- AD / SSO authentication
- Richer EVTX & dump parsing (built-in WinDbg-lite)
- Case sharing workflows
- Template packs per category
- Offline / on-prem model support
- Scheduled retention purge
