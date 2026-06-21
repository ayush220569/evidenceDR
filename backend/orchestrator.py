"""Orchestrator Agent — large-log investigation via map-reduce + self-critique + persistent memory.

Phases:
  1. PLAN    — gather all indexed chunks, group into batches, retrieve prior-case knowledge
  2. MAP     — per-batch LLM call: extract events, errors, anomalies, evidence excerpts (parallel)
  3. REDUCE  — single LLM call: synthesize final structured report from all map outputs + context + priors
  4. CRITIQUE — LLM self-critique against the evidence, refine the report
  5. MEMORY  — fingerprint root cause + signature errors, persist to case_patterns collection

This module is provider-agnostic: it takes a callable `chat_call(system, user) -> str` so the caller
(in server.py) can wire it to whatever Emergent LLM provider is configured for Provider A.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, List

from emergentintegrations.llm.chat import LlmChat, UserMessage


logger = logging.getLogger(__name__)

# ---- Configuration ----
DEFAULT_MAP_BATCH_SIZE = 25       # chunks per map call
DEFAULT_MAP_PARALLELISM = 6       # concurrent map calls
MAX_MAP_BATCHES = 12              # hard cap to keep cost predictable
MAX_PRIOR_PATTERNS = 4            # how many past-case patterns to surface as priors
MAP_EXCERPT_CHARS = 1200          # snippet cap per chunk inside map prompt
CRITIQUE_EVIDENCE_SAMPLE = 25     # chunks resampled for the critique pass


# ---- Prompts ----
MAP_SYSTEM = """You are a forensic log-analysis sub-agent. Extract evidence — do not speculate.

For each chunk you receive, identify:
- ERROR / FATAL / EXCEPTION lines (verbatim)
- WARN lines that hint at the root cause
- ANOMALIES (e.g. unusual gaps, repeated retries, auth failures, permission denials, status code spikes)
- KEY TIMESTAMPS for the incident window
- Short verbatim EVIDENCE EXCERPTS that future agents can cite

Output STRICT JSON only:
{
  "errors":   [{"file": "string", "chunk_index": int, "line_hint": "string", "excerpt": "verbatim (max 280 chars)"}],
  "warnings": [{"file": "string", "chunk_index": int, "excerpt": "string"}],
  "anomalies":[{"file": "string", "description": "string", "evidence": "string"}],
  "timestamps":[{"file": "string", "ts": "ISO8601 or as-written", "note": "string"}],
  "summary":  "string — 1-2 sentence batch-level summary"
}
If a chunk has nothing notable, omit it. Never invent events that aren't in the chunks."""

REDUCE_SYSTEM = """You are a senior support engineer synthesizing a final investigation report from sub-agent findings.

You will receive:
- The case context (category, symptoms, repro, recent changes)
- Patterns from similar past cases (prior knowledge)
- Per-batch findings from the map phase: errors, warnings, anomalies, timestamps

Produce a STRICT JSON investigation report with this schema:
{
  "overview": "string — 2-4 sentences. What broke, when, where in the stack.",
  "key_findings": [
    {"finding": "string", "evidence": ["verbatim excerpt or filename:chunk reference"], "confidence": "low|medium|high"}
  ],
  "timeline": [
    {"ts": "as-written timestamp", "event": "string", "evidence_ref": "filename:chunk"}
  ],
  "root_cause": {
    "primary_hypothesis": "string",
    "supporting_evidence": ["string"],
    "alternative_hypotheses": ["string"],
    "confidence": "low|medium|high"
  },
  "recommendations": ["imperative, specific action"],
  "likely_layer": "browser|web_tier|portal|server|datastore|client_pro|os_system|unknown",
  "gaps": ["evidence still needed to fully confirm"]
}

Rules:
- Every finding MUST cite at least one evidence excerpt or filename:chunk ref.
- Never invent timestamps, error messages, or events.
- If multiple prior cases match, mention which pattern applies but do not assume it.
- Order timeline chronologically.
- Confidence calibrated to evidence quality, NOT to your eloquence.
- Confidence calibrated to evidence quality, NOT to your eloquence.
- `likely_layer` is a CONTROLLED VOCABULARY — pick exactly one of the 8 allowed tokens. Do not invent descriptive strings."""

CRITIQUE_SYSTEM = """You are a critical reviewer auditing a peer's investigation report.

You will receive:
- The DRAFT report (JSON)
- A fresh sample of EVIDENCE chunks pulled directly from the indexed log

Your job: find weak claims, hallucinations, and gaps. Then produce a REFINED report in the SAME JSON schema as the draft.

Rules:
- If a finding's evidence is not present in the evidence sample AND looks fabricated, REMOVE IT or downgrade confidence to "low" with a note in `gaps`.
- If a strong piece of evidence in the sample is missing from the draft, ADD IT.
- Preserve the draft's overall structure; only adjust where evidence demands it.
- Set a top-level field `revisions` listing what you changed and why.

Output STRICT JSON matching the draft schema PLUS a `revisions` array of strings."""


# ---- Provider wiring ----
def _make_caller(api_key: str, model_provider: str, model_name: str, system: str) -> Callable[[str], Awaitable[str]]:
    """Build an async caller bound to one system prompt. New session per call (no leakage)."""
    async def _call(user_prompt: str) -> str:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"orchestrator-{uuid.uuid4()}",
            system_message=system,
        ).with_model(model_provider, model_name)
        return await chat.send_message(UserMessage(text=user_prompt))
    return _call


def _extract_json(text: str) -> dict:
    if not text:
        return {"_error": "empty response"}
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {"_error": "no json", "_raw": text[:500]}
    try:
        return json.loads(text[s:e + 1])
    except Exception as ex:
        return {"_error": f"parse failed: {ex}", "_raw": text[s:e + 1][:500]}


# ---- Phase 1: PLAN ----
def _batch_chunks(chunks: List[dict], batch_size: int = DEFAULT_MAP_BATCH_SIZE, max_batches: int = MAX_MAP_BATCHES) -> List[List[dict]]:
    """Group chunks into batches for map calls, capped at max_batches."""
    if not chunks:
        return []
    batches = [chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)]
    return batches[:max_batches]


def _format_batch_for_map(batch: List[dict]) -> str:
    lines = []
    for r in batch:
        lines.append(f"\n--- {r.get('file_name','?')} (chunk {r.get('chunk_index','?')}, score {r.get('score',0):.3f}, layer {r.get('layer','unknown')}) ---")
        text = r.get("text") or r.get("preview") or ""
        lines.append(text[:MAP_EXCERPT_CHARS])
    return "\n".join(lines)


def _format_priors(priors: List[dict]) -> str:
    if not priors:
        return "(no prior cases on file for this category)"
    out = []
    for p in priors[:MAX_PRIOR_PATTERNS]:
        out.append(
            f"- Prior case (category={p.get('category_id')}, layer={p.get('layer')}): "
            f"root_cause=\"{p.get('root_cause_summary','?')}\"; "
            f"signature_errors={p.get('signature_errors', [])[:3]}; "
            f"recommendations={p.get('recommendations', [])[:3]}"
        )
    return "\n".join(out)


# ---- Phase 2: MAP ----
async def _map_phase(batches: List[List[dict]], caller: Callable[[str], Awaitable[str]],
                     parallelism: int = DEFAULT_MAP_PARALLELISM) -> List[dict]:
    sem = asyncio.Semaphore(parallelism)

    async def _one(batch: List[dict], idx: int) -> dict:
        async with sem:
            user = f"BATCH {idx + 1}/{len(batches)} — {len(batch)} chunks\n{_format_batch_for_map(batch)}"
            try:
                resp = await caller(user)
                parsed = _extract_json(resp)
                parsed["_batch_index"] = idx
                parsed["_chunk_count"] = len(batch)
                return parsed
            except Exception as e:
                logger.exception(f"map batch {idx} failed: {e}")
                return {"_error": str(e), "_batch_index": idx}

    return await asyncio.gather(*[_one(b, i) for i, b in enumerate(batches)])


# ---- Phase 3: REDUCE ----
def _format_map_findings(map_outputs: List[dict]) -> str:
    parts = []
    for m in map_outputs:
        if m.get("_error"):
            parts.append(f"\n[Batch {m.get('_batch_index')}: ERROR — {m['_error']}]")
            continue
        parts.append(f"\n=== Batch {m.get('_batch_index')} ({m.get('_chunk_count')} chunks) ===")
        if m.get("summary"):
            parts.append(f"Summary: {m['summary']}")
        for e in m.get("errors", [])[:8]:
            parts.append(f"  ERROR @ {e.get('file')}:ch{e.get('chunk_index')} — {e.get('excerpt','')}")
        for w in m.get("warnings", [])[:5]:
            parts.append(f"  WARN @ {w.get('file')}:ch{w.get('chunk_index')} — {w.get('excerpt','')}")
        for a in m.get("anomalies", [])[:5]:
            parts.append(f"  ANOMALY @ {a.get('file')} — {a.get('description','')} | evidence: {a.get('evidence','')}")
        for t in m.get("timestamps", [])[:5]:
            parts.append(f"  TIME {t.get('ts')} — {t.get('note','')} ({t.get('file')})")
    return "\n".join(parts)


async def _reduce_phase(case: dict, map_outputs: List[dict], priors: List[dict],
                        caller: Callable[[str], Awaitable[str]]) -> dict:
    ctx = case.get("context", {}) or {}
    user = f"""CASE CONTEXT
Title: {case.get('title','')}
Category: {case.get('category_name','')}
Summary: {ctx.get('summary','')}
Timestamps + TZ: {ctx.get('timestamps','(missing)')}
Versions: {ctx.get('versions','(missing)')}
Topology: {ctx.get('topology','(missing)')}
Recent changes: {ctx.get('recent_changes','(missing)')}
Repro steps: {ctx.get('repro_steps','(missing)')}

PRIOR-CASE PATTERNS (apply only if evidence supports them):
{_format_priors(priors)}

MAP-PHASE FINDINGS (extracted by sub-agents from each chunk batch):
{_format_map_findings(map_outputs)}

Produce the final structured investigation report (STRICT JSON per your schema)."""
    resp = await caller(user)
    return _extract_json(resp)


# ---- Phase 4: CRITIQUE ----
async def _critique_phase(draft: dict, evidence_sample: List[dict],
                          caller: Callable[[str], Awaitable[str]]) -> dict:
    user = f"""DRAFT REPORT (JSON):
{json.dumps(draft, indent=2)[:12000]}

EVIDENCE SAMPLE ({len(evidence_sample)} freshly retrieved chunks):
{_format_batch_for_map(evidence_sample)}

Audit the draft and output the refined report (STRICT JSON, same schema + `revisions` array)."""
    resp = await caller(user)
    refined = _extract_json(resp)
    if refined.get("_error"):
        # If critique fails, return draft unchanged with a note
        draft["revisions"] = [f"Critique pass failed: {refined.get('_error')}. Draft preserved as-is."]
        return draft
    return refined


# ---- Phase 5: MEMORY ----
def fingerprint_from_report(report: dict, case: dict) -> dict:
    rc = (report or {}).get("root_cause") or {}
    sig_errors = []
    for f in (report or {}).get("key_findings", [])[:6]:
        for ev in (f.get("evidence") or [])[:2]:
            if ev and len(ev) < 280:
                sig_errors.append(ev)
    return {
        "id": str(uuid.uuid4()),
        "case_id": case.get("id"),
        "category_id": case.get("category_id"),
        "layer": report.get("likely_layer", "unknown"),
        "root_cause_summary": rc.get("primary_hypothesis", ""),
        "supporting_evidence": (rc.get("supporting_evidence") or [])[:4],
        "signature_errors": sig_errors[:8],
        "recommendations": (report.get("recommendations") or [])[:5],
        "confidence": rc.get("confidence", "low"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---- Public orchestrate() ----
async def orchestrate(
    case: dict,
    all_chunks: List[dict],
    priors: List[dict],
    evidence_sample: List[dict],
    api_key: str,
    model_provider: str,
    model_name: str,
) -> dict:
    """Run the full 4-phase orchestrator pipeline and return a structured result.

    Args:
        case: the case document (dict) from MongoDB
        all_chunks: chunks to feed into the MAP phase (already filtered/ranked)
        priors: list of past case_pattern docs (already filtered by category)
        evidence_sample: a separate sample of chunks for the CRITIQUE phase
        api_key, model_provider, model_name: LLM wiring (e.g. Emergent key + openai + gpt-5.5)

    Returns a dict with keys: status, phases, report, fingerprint, stats, started_at, finished_at.
    """
    started = datetime.now(timezone.utc).isoformat()
    stats = {
        "total_chunks_available": len(all_chunks),
        "priors_used": min(len(priors), MAX_PRIOR_PATTERNS),
    }

    # Phase 1: PLAN — batch the chunks
    batches = _batch_chunks(all_chunks)
    stats["map_batches"] = len(batches)
    stats["chunks_mapped"] = sum(len(b) for b in batches)

    if not batches:
        return {
            "status": "no_evidence",
            "report": None,
            "stats": stats,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "phases": ["plan"],
            "fingerprint": None,
        }

    map_caller = _make_caller(api_key, model_provider, model_name, MAP_SYSTEM)
    reduce_caller = _make_caller(api_key, model_provider, model_name, REDUCE_SYSTEM)
    critique_caller = _make_caller(api_key, model_provider, model_name, CRITIQUE_SYSTEM)

    # Phase 2: MAP
    map_outputs = await _map_phase(batches, map_caller)

    # Phase 3: REDUCE
    draft = await _reduce_phase(case, map_outputs, priors, reduce_caller)
    if draft.get("_error"):
        return {
            "status": "reduce_failed",
            "report": None,
            "draft_error": draft.get("_error"),
            "map_outputs": map_outputs,
            "stats": stats,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "phases": ["plan", "map", "reduce"],
            "fingerprint": None,
        }

    # Phase 4: CRITIQUE
    refined = await _critique_phase(draft, evidence_sample, critique_caller)

    # Coerce likely_layer to controlled vocab (defensive — sometimes LLMs paraphrase)
    _ALLOWED_LAYERS = {"browser", "web_tier", "portal", "server", "datastore", "client_pro", "os_system", "unknown"}
    if refined.get("likely_layer") not in _ALLOWED_LAYERS:
        guess = (refined.get("likely_layer") or "").lower()
        coerced = "unknown"
        for token in _ALLOWED_LAYERS:
            if token in guess.replace("-", "_"):
                coerced = token
                break
        refined["likely_layer_raw"] = refined.get("likely_layer")
        refined["likely_layer"] = coerced

    # Phase 5: MEMORY fingerprint (caller persists it)
    fp = fingerprint_from_report(refined, case)

    return {
        "status": "done",
        "report": refined,
        "draft": draft,
        "fingerprint": fp,
        "map_outputs": map_outputs,
        "stats": stats,
        "model": f"{model_provider}/{model_name}",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "phases": ["plan", "map", "reduce", "critique", "memory"],
    }
