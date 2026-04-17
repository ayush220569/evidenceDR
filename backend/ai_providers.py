"""Dual AI provider abstraction. Both providers use emergentintegrations + Emergent Universal LLM Key by default,
but can be overridden by user-supplied keys (OpenAI-compatible & Microsoft/Azure-OpenAI-compatible)."""
import os
import json
import re
import uuid
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage


SYSTEM_PROMPT = """You are EvidencePilot, an expert ArcGIS / ArcGIS Enterprise / ArcGIS Pro support triage assistant.

You help support engineers triage logs and evidence. You MUST follow these rules strictly:

1. Never claim certainty without evidence. If logs are insufficient, say so clearly.
2. Distinguish: observed evidence (from uploaded files) vs inference (your reasoning) vs missing evidence (what would confirm/refute).
3. Cite which uploaded files (by name) support each conclusion.
4. Prefer precise, support-friendly language. No hype, no marketing tone.
5. Reinforce these principles when relevant:
   - Hangs need Diagnostic Monitor (not just dumps)
   - Path/permission errors justify ProcMon
   - WebGISDR scheduled-fails-only is usually service-account permission or sleep/wake
   - If direct 7443/6443 works while Web Adaptor fails, focus on the front-door
   - Crashes need .dmp + Event Viewer + Pro build + GPU driver
   - Always reinforce that timestamps with timezone, repro steps, exact URLs, versions, topology, and recent changes are MANDATORY context
6. Output strictly valid JSON in the requested schema. No prose outside the JSON.
"""

OUTPUT_SCHEMA = {
    "triage_summary": "string - 2-4 sentences plain-English summary",
    "likely_layer": "one of: browser | web_tier | portal | server | datastore | client_pro | os_system | unknown",
    "ranked_hypotheses": [
        {"hypothesis": "string", "confidence": "low|medium|high", "supporting_evidence": ["filename or context field"], "missing_evidence": ["string"]}
    ],
    "evidence_gaps": ["string"],
    "next_collection_steps": ["string - imperative, specific (e.g. 'Capture HAR with Preserve Log enabled during reproduction')"],
    "packaging_structure": {
        "Browser": ["string"],
        "Web tier": ["string"],
        "Portal": ["string"],
        "Server": ["string"],
        "Data Store": ["string"],
        "Pro client": ["string"],
        "OS / System": ["string"]
    },
    "customer_summary": "string - 3-5 sentences, customer-facing, no jargon",
    "internal_escalation_summary": "string - 5-8 sentences, technical, includes facts + open questions",
    "confidence_score": "integer 0-100",
    "narrative_5_line": {
        "what_broke": "string",
        "when_it_broke": "string",
        "what_changed": "string",
        "reproduction_steps": "string",
        "already_ruled_out": "string"
    }
}


def build_user_prompt(case: dict, file_excerpts: list) -> str:
    ctx = case.get("context", {}) or {}
    cat = case.get("category_name", "Unknown")
    logic = case.get("logic_answers", []) or []
    logic_str = "\n".join([f"  - Q: {a.get('question')} -> A: {a.get('answer_label')}" for a in logic]) or "  (no logic tree answered yet)"

    files_block = ""
    if file_excerpts:
        for fe in file_excerpts:
            files_block += f"\n--- FILE: {fe['name']} (layer={fe.get('layer','unknown')}, size={fe.get('size',0)} bytes) ---\n"
            files_block += fe.get("excerpt", "(no text extracted)")[:4000]
            files_block += "\n"
    else:
        files_block = "\n(no files uploaded yet)\n"

    return f"""CASE CONTEXT
Case title: {case.get('title','(untitled)')}
Issue category: {cat}
Short summary: {ctx.get('summary','(none)')}
Timestamps + timezone: {ctx.get('timestamps','(MISSING)')}
Exact URLs: {ctx.get('urls','(MISSING)')}
Software / product versions: {ctx.get('versions','(MISSING)')}
Deployment topology: {ctx.get('topology','(MISSING)')}
Recent changes: {ctx.get('recent_changes','(MISSING)')}
Reproduction steps: {ctx.get('repro_steps','(MISSING)')}
Already-tested actions: {ctx.get('already_tested','(none)')}
Customer environment notes: {ctx.get('environment_notes','(none)')}

LOGIC TREE ANSWERS
{logic_str}

UPLOADED FILES (text excerpts, truncated):
{files_block}

TASK
Analyze the above and respond with STRICTLY VALID JSON matching this schema:
{json.dumps(OUTPUT_SCHEMA, indent=2)}

Remember: cite specific filenames in supporting_evidence. If evidence is missing, populate evidence_gaps and missing_evidence accordingly. Confidence must be calibrated to evidence quality.
"""


def _extract_json(text: str) -> dict:
    """Extract JSON from model response (handles ```json fences)."""
    if not text:
        return {"_error": "empty response"}
    # Strip code fences
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    # Find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"_error": "no json object found", "_raw": text[:500]}
    blob = text[start:end + 1]
    try:
        return json.loads(blob)
    except Exception as e:
        return {"_error": f"json parse failed: {e}", "_raw": blob[:500]}


async def run_provider(provider_label: str, model_provider: str, model_name: str, case: dict, file_excerpts: list,
                       api_key_override: Optional[str] = None) -> dict:
    """Run a single provider analysis. Returns dict with provider info + parsed JSON output."""
    api_key = api_key_override or os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {
            "provider_label": provider_label,
            "model": f"{model_provider}/{model_name}",
            "error": "No API key configured (EMERGENT_LLM_KEY missing and no override).",
            "output": None,
        }

    session_id = f"evidencepilot-{uuid.uuid4()}"
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=SYSTEM_PROMPT,
        ).with_model(model_provider, model_name)

        prompt = build_user_prompt(case, file_excerpts)
        response_text = await chat.send_message(UserMessage(text=prompt))
        parsed = _extract_json(response_text)
        return {
            "provider_label": provider_label,
            "model": f"{model_provider}/{model_name}",
            "output": parsed,
            "raw": response_text[:2000] if isinstance(response_text, str) else str(response_text)[:2000],
        }
    except Exception as e:
        return {
            "provider_label": provider_label,
            "model": f"{model_provider}/{model_name}",
            "error": f"Provider call failed: {e}",
            "output": None,
        }


def compute_disagreement(out_a: dict, out_b: dict) -> dict:
    """Compare two provider outputs."""
    a = (out_a or {}).get("output") or {}
    b = (out_b or {}).get("output") or {}

    def _safe_list(v):
        return v if isinstance(v, list) else []

    layer_a = a.get("likely_layer", "?")
    layer_b = b.get("likely_layer", "?")

    hypos_a = {(h.get("hypothesis") or "").strip().lower() for h in _safe_list(a.get("ranked_hypotheses"))}
    hypos_b = {(h.get("hypothesis") or "").strip().lower() for h in _safe_list(b.get("ranked_hypotheses"))}

    only_a = sorted(hypos_a - hypos_b)
    only_b = sorted(hypos_b - hypos_a)
    shared = sorted(hypos_a & hypos_b)

    conf_a = a.get("confidence_score", 0) or 0
    conf_b = b.get("confidence_score", 0) or 0

    return {
        "layer_agreement": layer_a == layer_b,
        "layer_a": layer_a,
        "layer_b": layer_b,
        "only_in_a": only_a,
        "only_in_b": only_b,
        "shared": shared,
        "confidence_delta": abs(conf_a - conf_b),
        "confidence_a": conf_a,
        "confidence_b": conf_b,
    }
