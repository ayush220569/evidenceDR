"""EvidencePilot AI - FastAPI backend."""
import asyncio
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import json
import shutil
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

from rules import CATEGORIES, LAYERS, CONTEXT_FIELDS, get_logic_tree, score_evidence
from ai_providers import run_provider, compute_disagreement
from file_utils import extract_text, detect_layer, safe_extract_zip


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/backend/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="EvidencePilot AI")
api = APIRouter(prefix="/api")


# ------------------ Models ------------------
class ContextData(BaseModel):
    summary: Optional[str] = ""
    timestamps: Optional[str] = ""
    urls: Optional[str] = ""
    versions: Optional[str] = ""
    topology: Optional[str] = ""
    recent_changes: Optional[str] = ""
    repro_steps: Optional[str] = ""
    already_tested: Optional[str] = ""
    environment_notes: Optional[str] = ""


class CaseCreate(BaseModel):
    title: str
    category_id: str
    context: Optional[ContextData] = None
    symptom_clues: Optional[List[str]] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    category_id: Optional[str] = None
    context: Optional[ContextData] = None
    symptom_clues: Optional[List[str]] = None
    status: Optional[str] = None


class LogicAnswer(BaseModel):
    node_id: str
    question: str
    answer_value: str
    answer_label: str


class AnalyzeRequest(BaseModel):
    use_provider_a: bool = True
    use_provider_b: bool = True


class SettingsModel(BaseModel):
    provider_a_label: str = "OpenAI GPT-5.2"
    provider_a_model: str = "gpt-5.2"
    provider_a_provider: str = "openai"
    provider_a_api_key: Optional[str] = ""
    provider_b_label: str = "Microsoft / Copilot-style (Claude Sonnet 4.5)"
    provider_b_model: str = "claude-sonnet-4-5-20250929"
    provider_b_provider: str = "anthropic"
    provider_b_api_key: Optional[str] = ""
    retention_days: int = 30
    max_upload_mb: int = 512
    escalation_contact: str = "corp.support.help@esri.ca"


# ------------------ Helpers ------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def case_dir(case_id: str) -> Path:
    d = UPLOAD_DIR / case_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name)
    return name[:200] or f"file-{uuid.uuid4().hex[:8]}"


async def get_settings_doc() -> dict:
    doc = await db.settings.find_one({"_id": "global"}, {"_id": 0})
    if not doc:
        s = SettingsModel().model_dump()
        await db.settings.update_one({"_id": "global"}, {"$set": s}, upsert=True)
        return s
    return doc


def case_to_response(c: dict) -> dict:
    if not c:
        return c
    return {k: v for k, v in c.items() if k != "_id"}


# ------------------ Routes ------------------
@api.get("/")
async def root():
    return {"app": "EvidencePilot AI", "status": "ok", "time": now_iso()}


@api.get("/categories")
async def list_categories():
    return {"categories": list(CATEGORIES.values()), "layers": LAYERS, "context_fields": CONTEXT_FIELDS}


@api.get("/categories/{category_id}/logic-tree")
async def get_tree(category_id: str):
    return {"category_id": category_id, "tree": get_logic_tree(category_id)}


# ---- Cases ----
@api.post("/cases")
async def create_case(payload: CaseCreate):
    if payload.category_id not in CATEGORIES:
        raise HTTPException(400, f"Unknown category_id: {payload.category_id}")
    cat = CATEGORIES[payload.category_id]
    case_id = str(uuid.uuid4())
    doc = {
        "id": case_id,
        "title": payload.title,
        "category_id": payload.category_id,
        "category_name": cat["name"],
        "context": (payload.context.model_dump() if payload.context else ContextData().model_dump()),
        "symptom_clues": payload.symptom_clues or [],
        "files": [],
        "logic_answers": [],
        "ai_results": {"provider_a": None, "provider_b": None, "disagreement": None, "ran_at": None},
        "status": "open",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.cases.insert_one({**doc, "_id": case_id})
    return case_to_response(doc)


@api.get("/cases")
async def list_cases(status: Optional[str] = None, limit: int = 100):
    q = {}
    if status:
        q["status"] = status
    cursor = db.cases.find(q, {"_id": 0}).sort("updated_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    for c in items:
        c["score"] = score_evidence(c)
    return {"cases": items}


@api.get("/cases/{case_id}")
async def get_case(case_id: str):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    c["score"] = score_evidence(c)
    return c


@api.patch("/cases/{case_id}")
async def update_case(case_id: str, payload: CaseUpdate):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    upd: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.title is not None:
        upd["title"] = payload.title
    if payload.category_id is not None:
        if payload.category_id not in CATEGORIES:
            raise HTTPException(400, "Unknown category_id")
        upd["category_id"] = payload.category_id
        upd["category_name"] = CATEGORIES[payload.category_id]["name"]
    if payload.context is not None:
        upd["context"] = payload.context.model_dump()
    if payload.symptom_clues is not None:
        upd["symptom_clues"] = payload.symptom_clues
    if payload.status is not None:
        upd["status"] = payload.status
    await db.cases.update_one({"id": case_id}, {"$set": upd})
    c2 = await db.cases.find_one({"id": case_id}, {"_id": 0})
    c2["score"] = score_evidence(c2)
    return c2


@api.delete("/cases/{case_id}")
async def delete_case(case_id: str):
    await db.cases.delete_one({"id": case_id})
    d = UPLOAD_DIR / case_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    return {"deleted": case_id}


# ---- Files ----
@api.post("/cases/{case_id}/files")
async def upload_files(case_id: str, files: List[UploadFile] = File(...), layer: Optional[str] = Form(None)):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    settings = await get_settings_doc()
    max_bytes = int(settings.get("max_upload_mb", 512)) * 1024 * 1024

    saved = []
    cdir = case_dir(case_id)
    for uf in files:
        safe_name = sanitize_filename(uf.filename or "upload")
        fid = uuid.uuid4().hex[:10]
        target = cdir / f"{fid}_{safe_name}"
        size = 0
        with open(target, "wb") as out:
            while True:
                chunk = await uf.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, f"File {safe_name} exceeds max upload size of {settings['max_upload_mb']}MB")
                out.write(chunk)

        excerpt = extract_text(str(target), max_bytes=20000)
        detected = layer if layer and layer in LAYERS else detect_layer(safe_name, excerpt)
        meta = {
            "id": fid,
            "name": safe_name,
            "stored_path": str(target),
            "size": size,
            "ext": Path(safe_name).suffix.lower(),
            "layer": detected,
            "uploaded_at": now_iso(),
        }
        saved.append(meta)

    await db.cases.update_one(
        {"id": case_id},
        {"$push": {"files": {"$each": saved}}, "$set": {"updated_at": now_iso()}},
    )
    c2 = await db.cases.find_one({"id": case_id}, {"_id": 0})
    c2["score"] = score_evidence(c2)
    return {"uploaded": saved, "case": c2}


@api.delete("/cases/{case_id}/files/{file_id}")
async def delete_file(case_id: str, file_id: str):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    files = c.get("files", [])
    target = next((f for f in files if f["id"] == file_id), None)
    if not target:
        raise HTTPException(404, "File not found")
    try:
        Path(target["stored_path"]).unlink(missing_ok=True)
    except Exception:
        pass
    await db.cases.update_one({"id": case_id}, {"$pull": {"files": {"id": file_id}}, "$set": {"updated_at": now_iso()}})
    return {"deleted": file_id}


@api.patch("/cases/{case_id}/files/{file_id}")
async def update_file_layer(case_id: str, file_id: str, layer: str = Form(...)):
    if layer not in LAYERS:
        raise HTTPException(400, "Unknown layer")
    res = await db.cases.update_one(
        {"id": case_id, "files.id": file_id},
        {"$set": {"files.$.layer": layer, "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "File not found")
    return {"ok": True, "layer": layer}


@api.get("/cases/{case_id}/files/{file_id}/preview")
async def preview_file(case_id: str, file_id: str, max_bytes: int = 20000):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    target = next((f for f in c.get("files", []) if f["id"] == file_id), None)
    if not target:
        raise HTTPException(404, "File not found")
    text = extract_text(target["stored_path"], max_bytes=max_bytes)
    return {"name": target["name"], "size": target["size"], "layer": target["layer"], "text": text}


@api.post("/cases/{case_id}/files/{file_id}/extract")
async def extract_zip(case_id: str, file_id: str):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    target = next((f for f in c.get("files", []) if f["id"] == file_id), None)
    if not target or target.get("ext") != ".zip":
        raise HTTPException(400, "Not a zip file")
    cdir = case_dir(case_id) / f"extracted_{file_id}"
    members = safe_extract_zip(target["stored_path"], str(cdir))
    new_files = []
    for m in members:
        name = sanitize_filename(Path(m).name)
        size = os.path.getsize(m)
        excerpt = extract_text(m, max_bytes=20000)
        detected = detect_layer(name, excerpt)
        new_files.append({
            "id": uuid.uuid4().hex[:10],
            "name": name,
            "stored_path": m,
            "size": size,
            "ext": Path(name).suffix.lower(),
            "layer": detected,
            "uploaded_at": now_iso(),
            "from_zip": target["name"],
        })
    if new_files:
        await db.cases.update_one({"id": case_id}, {"$push": {"files": {"$each": new_files}}})
    return {"extracted": new_files}


# ---- Logic Tree ----
@api.post("/cases/{case_id}/logic")
async def save_logic_answers(case_id: str, answers: List[LogicAnswer]):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    payload = [a.model_dump() for a in answers]
    await db.cases.update_one(
        {"id": case_id},
        {"$set": {"logic_answers": payload, "updated_at": now_iso()}},
    )
    c2 = await db.cases.find_one({"id": case_id}, {"_id": 0})
    c2["score"] = score_evidence(c2)
    return c2


# ---- Score ----
@api.get("/cases/{case_id}/score")
async def get_score(case_id: str):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    return score_evidence(c)


# ---- AI Analyze ----
async def _run_analysis_job(case_id: str, use_a: bool, use_b: bool):
    """Background job: runs both providers in parallel, persists result."""
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        return
    settings = await get_settings_doc()

    excerpts = []
    total_chars = 0
    cap = 30_000
    for f in c.get("files", []):
        if total_chars >= cap:
            break
        text = extract_text(f["stored_path"], max_bytes=8000)
        if total_chars + len(text) > cap:
            text = text[: max(0, cap - total_chars)]
        excerpts.append({"name": f["name"], "layer": f.get("layer", "unknown"), "size": f.get("size", 0), "excerpt": text})
        total_chars += len(text)

    async def _maybe(call):
        return await call

    coros = []
    if use_a:
        coros.append(run_provider(
            provider_label=settings.get("provider_a_label", "OpenAI GPT-5.2"),
            model_provider=settings.get("provider_a_provider", "openai"),
            model_name=settings.get("provider_a_model", "gpt-5.2"),
            case=c, file_excerpts=excerpts,
            api_key_override=(settings.get("provider_a_api_key") or None),
        ))
    if use_b:
        coros.append(run_provider(
            provider_label=settings.get("provider_b_label", "Microsoft / Copilot-style (Claude Sonnet 4.5)"),
            model_provider=settings.get("provider_b_provider", "anthropic"),
            model_name=settings.get("provider_b_model", "claude-sonnet-4-5-20250929"),
            case=c, file_excerpts=excerpts,
            api_key_override=(settings.get("provider_b_api_key") or None),
        ))

    out = await asyncio.gather(*coros, return_exceptions=True)
    results = c.get("ai_results", {}) or {}
    idx = 0
    if use_a:
        v = out[idx]; idx += 1
        results["provider_a"] = v if not isinstance(v, Exception) else {"error": f"job error: {v}", "output": None, "model": "?", "provider_label": "Provider A"}
    if use_b:
        v = out[idx]; idx += 1
        results["provider_b"] = v if not isinstance(v, Exception) else {"error": f"job error: {v}", "output": None, "model": "?", "provider_label": "Provider B"}
    results["disagreement"] = compute_disagreement(results.get("provider_a"), results.get("provider_b"))
    results["ran_at"] = now_iso()
    results["status"] = "done"
    await db.cases.update_one({"id": case_id}, {"$set": {"ai_results": results, "updated_at": now_iso()}})


@api.post("/cases/{case_id}/analyze")
async def analyze_case(case_id: str, req: AnalyzeRequest, background: BackgroundTasks):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    # Mark running and dispatch — returns fast to avoid ingress timeouts on long LLM calls
    results = c.get("ai_results", {}) or {}
    results["status"] = "running"
    results["started_at"] = now_iso()
    await db.cases.update_one({"id": case_id}, {"$set": {"ai_results": results, "updated_at": now_iso()}})
    background.add_task(_run_analysis_job, case_id, req.use_provider_a, req.use_provider_b)
    return {"status": "running", "case_id": case_id, "started_at": results["started_at"]}


@api.get("/cases/{case_id}/analyze/status")
async def analyze_status(case_id: str):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    ai = c.get("ai_results") or {}
    return {
        "status": ai.get("status") or ("done" if ai.get("ran_at") else "idle"),
        "ran_at": ai.get("ran_at"),
        "started_at": ai.get("started_at"),
        "has_a": bool(ai.get("provider_a")),
        "has_b": bool(ai.get("provider_b")),
    }


# ---- Settings ----
@api.get("/settings")
async def get_settings():
    s = await get_settings_doc()
    masked = dict(s)
    for k in ("provider_a_api_key", "provider_b_api_key"):
        v = masked.get(k) or ""
        masked[k] = ("•" * 8 + v[-4:]) if len(v) > 4 else ""
    masked["provider_a_api_key_set"] = bool(s.get("provider_a_api_key"))
    masked["provider_b_api_key_set"] = bool(s.get("provider_b_api_key"))
    return masked


@api.put("/settings")
async def update_settings(payload: SettingsModel):
    doc = payload.model_dump()
    existing = await db.settings.find_one({"_id": "global"}, {"_id": 0}) or {}
    if not doc.get("provider_a_api_key"):
        doc["provider_a_api_key"] = existing.get("provider_a_api_key", "")
    if not doc.get("provider_b_api_key"):
        doc["provider_b_api_key"] = existing.get("provider_b_api_key", "")
    await db.settings.update_one({"_id": "global"}, {"$set": doc}, upsert=True)
    return await get_settings()


# ---- Dashboard ----
@api.get("/dashboard/stats")
async def dashboard_stats():
    cases = await db.cases.find({}, {"_id": 0}).to_list(length=500)
    total = len(cases)
    open_n = sum(1 for c in cases if c.get("status") == "open")
    resolved_n = sum(1 for c in cases if c.get("status") == "resolved")
    analyzed_n = sum(1 for c in cases if (c.get("ai_results") or {}).get("ran_at"))
    by_cat: Dict[str, int] = {}
    avg_completeness_total = 0
    for c in cases:
        by_cat[c.get("category_id", "unknown")] = by_cat.get(c.get("category_id", "unknown"), 0) + 1
        avg_completeness_total += score_evidence(c)["overall_pct"]
    avg_completeness = round(avg_completeness_total / total) if total else 0
    return {
        "total": total,
        "open": open_n,
        "resolved": resolved_n,
        "analyzed": analyzed_n,
        "by_category": by_cat,
        "avg_completeness": avg_completeness,
    }


# ---- Export ----
def _build_report_dict(c: dict) -> dict:
    score = score_evidence(c)
    ai = c.get("ai_results") or {}
    return {
        "case": {
            "id": c.get("id"),
            "title": c.get("title"),
            "category": c.get("category_name"),
            "status": c.get("status"),
            "created_at": c.get("created_at"),
        },
        "context": c.get("context", {}),
        "symptom_clues": c.get("symptom_clues", []),
        "logic_answers": c.get("logic_answers", []),
        "files": [{k: v for k, v in f.items() if k != "stored_path"} for f in c.get("files", [])],
        "evidence_score": score,
        "ai": {
            "provider_a": ai.get("provider_a"),
            "provider_b": ai.get("provider_b"),
            "disagreement": ai.get("disagreement"),
            "ran_at": ai.get("ran_at"),
        },
    }


def _md_report(c: dict) -> str:
    r = _build_report_dict(c)
    case = r["case"]
    score = r["evidence_score"]
    ctx = r["context"]
    L: List[str] = []
    L.append(f"# EvidencePilot Report — {case['title']}")
    L.append("")
    L.append(f"- **Category:** {case['category']}")
    L.append(f"- **Status:** {case['status']}")
    L.append(f"- **Created:** {case['created_at']}")
    L.append(f"- **Evidence completeness:** {score['overall_pct']}% ({score['readiness']} readiness)")
    L.append("")
    L.append("## Key Context")
    for f in CONTEXT_FIELDS:
        L.append(f"- **{f['label']}:** {ctx.get(f['key'], '') or '_(missing)_'}")
    L.append("")
    L.append("## Symptom Clues")
    for s in r["symptom_clues"] or ["_(none)_"]:
        L.append(f"- {s}")
    L.append("")
    L.append("## Logic Tree Path")
    for a in r["logic_answers"] or []:
        L.append(f"- **{a['question']}** → {a['answer_label']}")
    if not r["logic_answers"]:
        L.append("_(not run)_")
    L.append("")
    L.append("## Files Collected")
    for f in r["files"]:
        L.append(f"- `{f['name']}` ({f.get('size',0)} bytes) — layer: **{f.get('layer','unknown')}**")
    if not r["files"]:
        L.append("_(no files)_")
    L.append("")
    L.append("## Evidence Gaps")
    for g in score["context_gaps"]:
        L.append(f"- Missing context: {g}")
    for ml in score["missing_layers"]:
        L.append(f"- Missing layer evidence: {ml}")
    if not score["context_gaps"] and not score["missing_layers"]:
        L.append("_(no major gaps detected)_")
    L.append("")
    for label, key in [("Provider A", "provider_a"), ("Provider B", "provider_b")]:
        p = (r["ai"] or {}).get(key)
        L.append(f"## AI {label}")
        if not p:
            L.append("_(not run)_")
            continue
        L.append(f"- **Model:** `{p.get('model','?')}` ({p.get('provider_label','')})")
        if p.get("error"):
            L.append(f"- **Error:** {p['error']}")
            continue
        out = p.get("output") or {}
        L.append(f"- **Likely layer:** {out.get('likely_layer','?')}")
        L.append(f"- **Confidence:** {out.get('confidence_score','?')}")
        L.append(f"- **Triage summary:** {out.get('triage_summary','')}")
        L.append("- **Ranked hypotheses:**")
        for h in (out.get("ranked_hypotheses") or []):
            L.append(f"  - {h.get('hypothesis')} ({h.get('confidence')})")
        L.append("- **Next collection steps:**")
        for s in (out.get("next_collection_steps") or []):
            L.append(f"  - {s}")
    L.append("")
    dis = (r["ai"] or {}).get("disagreement") or {}
    if dis:
        L.append("## Disagreement")
        L.append(f"- Layer agreement: **{dis.get('layer_agreement')}** (A: {dis.get('layer_a')}, B: {dis.get('layer_b')})")
        L.append(f"- Confidence delta: {dis.get('confidence_delta')}")
        if dis.get("only_in_a"):
            L.append(f"- Only in A: {', '.join(dis['only_in_a'])}")
        if dis.get("only_in_b"):
            L.append(f"- Only in B: {', '.join(dis['only_in_b'])}")
    L.append("")
    L.append("## Escalation Readiness Checklist")
    for f in CONTEXT_FIELDS:
        ok = bool((ctx.get(f["key"]) or "").strip())
        L.append(f"- [{'x' if ok else ' '}] {f['label']}")
    return "\n".join(L)


def _html_report(c: dict) -> str:
    md = _md_report(c)
    body = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>EvidencePilot Report — {c.get('title','')}</title>
<style>
body{{background:#0A0A0C;color:#fff;font-family:'DM Sans',-apple-system,sans-serif;padding:40px;max-width:900px;margin:auto}}
h1,h2,h3{{font-family:'Chivo',sans-serif;letter-spacing:-.02em}}
pre{{background:#121215;border:1px solid #27272A;padding:16px;white-space:pre-wrap;font-family:'JetBrains Mono',monospace;font-size:13px;line-height:1.5}}
@media print{{body{{background:#fff;color:#000}}pre{{background:#f5f5f5;color:#000;border-color:#ccc}}}}
</style></head><body><pre>{body}</pre></body></html>"""


@api.get("/cases/{case_id}/export")
async def export_case(case_id: str, format: str = Query("markdown", pattern="^(markdown|json|html)$")):
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")
    if format == "json":
        body = json.dumps(_build_report_dict(c), indent=2, default=str)
        return Response(body, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="evidencepilot-{case_id}.json"'})
    if format == "html":
        return Response(_html_report(c), media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="evidencepilot-{case_id}.html"'})
    return Response(_md_report(c), media_type="text/markdown",
                    headers={"Content-Disposition": f'attachment; filename="evidencepilot-{case_id}.md"'})


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db():
    client.close()
