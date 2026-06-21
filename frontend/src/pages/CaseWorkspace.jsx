import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiClient } from "../lib/api";
import { PageHeader, ProgressBar, SegmentedMeter, ConfidenceBadge, LayerTag, EmptyState } from "../components/UIBits";
import FileUploader from "../components/FileUploader";
import LogicTree from "../components/LogicTree";
import ProviderCard from "../components/ProviderCard";
import RetrievalPanel from "../components/RetrievalPanel";
import InvestigationReport from "../components/InvestigationReport";
import { Robot, Sparkle, Download, FileText, Code, Browsers, ArrowsClockwise, WarningCircle, CheckCircle, Detective } from "@phosphor-icons/react";

export default function CaseWorkspace() {
  const { id } = useParams();
  const nav = useNavigate();
  const [c, setC] = useState(null);
  const [meta, setMeta] = useState({ categories: [], layers: {} });
  const [tab, setTab] = useState("evidence");
  const [analyzing, setAnalyzing] = useState(false);
  const [investigating, setInvestigating] = useState(false);

  const reload = () => apiClient.getCase(id).then(setC);

  useEffect(() => {
    apiClient.getCase(id).then(setC);
    apiClient.getCategories().then(setMeta);
  }, [id]);

  if (!c) return <div className="px-8 py-10 text-[#71717A]">Loading case…</div>;

  const cat = meta.categories.find(x => x.id === c.category_id);
  const score = c.score || {};
  const aiA = c.ai_results?.provider_a;
  const aiB = c.ai_results?.provider_b;
  const dis = c.ai_results?.disagreement;

  const runAI = async () => {
    setAnalyzing(true);
    try {
      await apiClient.analyze(id, true, true);
      // poll status every 4s until done (or 5 min cap)
      const deadline = Date.now() + 5 * 60 * 1000;
      while (Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 4000));
        const s = await apiClient.analyzeStatus(id);
        if (s.status === "done") break;
      }
      const fresh = await apiClient.getCase(id);
      setC(fresh);
    } catch (e) {
      alert(`Analysis failed: ${e.response?.data?.detail || e.message}`);
    } finally { setAnalyzing(false); }
  };

  const runInvestigation = async () => {
    setInvestigating(true);
    setTab("investigation");
    try {
      await apiClient.orchestrate(id);
      // poll every 5s for up to 10 min (orchestrator does more LLM calls)
      const deadline = Date.now() + 10 * 60 * 1000;
      while (Date.now() < deadline) {
        // refresh case so the UI shows live phase progress
        const fresh = await apiClient.getCase(id);
        setC(fresh);
        const status = fresh.ai_results?.orchestrator?.status;
        if (status === "done" || status === "error" || status === "reduce_failed" || status === "no_evidence") break;
        await new Promise(r => setTimeout(r, 5000));
      }
    } catch (e) {
      alert(`Investigation failed: ${e.response?.data?.detail || e.message}`);
    } finally { setInvestigating(false); }
  };

  const setStatus = async (status) => {
    const res = await apiClient.updateCase(id, { status });
    setC(res);
  };

  return (
    <div data-testid="case-workspace-page">
      <PageHeader
        overline={`Case / ${cat?.short || c.category_id}`}
        title={c.title}
        subtitle={`Created ${new Date(c.created_at).toLocaleString()} · status: ${c.status}`}
        right={
          <>
            <button onClick={() => setStatus(c.status === "open" ? "resolved" : "open")} className="btn-ghost" data-testid="toggle-status-btn">
              {c.status === "open" ? "Mark resolved" : "Reopen"}
            </button>
            <button onClick={runAI} disabled={analyzing || investigating} className="btn-ghost" data-testid="run-ai-btn">
              <Robot size={14} weight="duotone" /> {analyzing ? "Analyzing…" : "Quick Dual-AI"}
            </button>
            <button onClick={runInvestigation} disabled={analyzing || investigating} className="btn-primary" data-testid="run-investigation-btn">
              <Detective size={14} weight="fill" /> {investigating ? "Investigating…" : "Deep Investigation"}
            </button>
          </>
        }
      />

      {/* Top metric strip */}
      <div className="grid grid-cols-1 md:grid-cols-4 border-b border-white/10">
        <Metric label="Evidence Completeness" value={`${score.overall_pct || 0}%`} bar={<ProgressBar value={score.overall_pct || 0} />} accent="#00E5FF" />
        <Metric label="First-Pass Readiness" value={(score.readiness || "low").toUpperCase()} bar={<SegmentedMeter value={score.overall_pct || 0} segments={12} />} accent={score.readiness === "high" ? "#10B981" : score.readiness === "medium" ? "#F59E0B" : "#EF4444"} />
        <Metric label="Files Collected" value={(c.files || []).length} />
        <Metric label="AI Status" value={c.ai_results?.ran_at ? "✓ COMPLETED" : "PENDING"} accent={c.ai_results?.ran_at ? "#10B981" : "#71717A"} />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/10 px-8 font-mono text-xs uppercase tracking-widest">
        {[
          ["evidence", "Evidence"],
          ["logic", "Logic Tree"],
          ["ai", "AI Comparison"],
          ["investigation", "Investigation"],
          ["gaps", "Gaps & Next Steps"],
          ["export", "Export"],
        ].map(([k, l]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-3 border-b-2 ${tab === k ? "border-[#00E5FF] text-[#00E5FF]" : "border-transparent text-[#71717A] hover:text-white"}`}
            data-testid={`tab-${k}`}
          >{l}</button>
        ))}
      </div>

      <div className="px-8 py-6">
        {tab === "evidence" && (
          <div className="space-y-6" data-testid="tab-content-evidence">
            <FileUploader caseId={id} files={c.files} layers={meta.layers} onChange={setC} />
            <ContextDisplay context={c.context} />
            {cat && (
              <div className="ep-card p-5">
                <div className="label-overline mb-2">Power-user tip for this category</div>
                <div className="font-mono text-sm text-[#A1A1AA]">{`// ${cat.tips}`}</div>
              </div>
            )}
          </div>
        )}

        {tab === "logic" && (
          <div data-testid="tab-content-logic">
            <LogicTree caseId={id} categoryId={c.category_id} initial={c.logic_answers} onSaved={setC} />
          </div>
        )}

        {tab === "ai" && (
          <div data-testid="tab-content-ai">
            {!aiA && !aiB ? (
              <EmptyState icon={Sparkle} title="No AI analysis yet" hint="Run the dual-AI pipeline to get side-by-side triage from two providers." action={<button onClick={runAI} disabled={analyzing} className="btn-primary" data-testid="ai-empty-run-btn"><Robot size={14} /> {analyzing ? "Running…" : "Run dual-AI"}</button>} />
            ) : (
              <div className="space-y-5">
                {c.ai_results?.retrieval && <RetrievalPanel r={c.ai_results.retrieval} layers={meta.layers} />}
                {dis && <DisagreementPanel d={dis} />}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <ProviderCard label="Provider A" data={aiA} />
                  <ProviderCard label="Provider B" data={aiB} />
                </div>
                <button onClick={runAI} disabled={analyzing} className="btn-ghost" data-testid="rerun-ai-btn">
                  <ArrowsClockwise size={14} /> {analyzing ? "Re-running…" : "Re-run analysis"}
                </button>
              </div>
            )}
          </div>
        )}

        {tab === "investigation" && (
          <div data-testid="tab-content-investigation" className="space-y-4">
            {!c.ai_results?.orchestrator ? (
              <EmptyState
                icon={Sparkle}
                title="No investigation yet"
                hint="Deep Investigation runs a 4-phase map-reduce + self-critique pipeline over up to 200 retrieved chunks. Slower than the quick dual-AI but evidence-grounded, with persistent memory across cases."
                action={<button onClick={runInvestigation} disabled={investigating} className="btn-primary" data-testid="investigation-empty-run-btn"><Detective size={14} weight="fill" /> {investigating ? "Running…" : "Run Deep Investigation"}</button>}
              />
            ) : (
              <>
                <InvestigationReport orch={c.ai_results.orchestrator} />
                {c.ai_results.orchestrator.status === "done" && (
                  <button onClick={runInvestigation} disabled={investigating} className="btn-ghost" data-testid="rerun-investigation-btn">
                    <ArrowsClockwise size={14} /> {investigating ? "Re-running…" : "Re-run investigation"}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {tab === "gaps" && (
          <div data-testid="tab-content-gaps" className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="ep-card p-5">
              <div className="label-overline mb-3">Missing Critical Evidence</div>
              {score.context_gaps?.length === 0 && score.missing_layers?.length === 0 ? (
                <div className="text-sm text-[#10B981] flex items-center gap-2"><CheckCircle weight="fill" /> No major gaps detected.</div>
              ) : (
                <>
                  {score.context_gaps?.map(g => (
                    <div key={g} className="diff-rem text-sm mb-2"><WarningCircle size={14} weight="fill" className="inline mr-1.5 text-[#EF4444]" />{g}</div>
                  ))}
                  {score.missing_layers?.map(l => (
                    <div key={l} className="diff-rem text-sm mb-2 font-mono"><WarningCircle size={14} weight="fill" className="inline mr-1.5 text-[#FF9F1C]" /> Layer evidence missing: <strong>{meta.layers?.[l]?.name || l}</strong></div>
                  ))}
                </>
              )}
            </div>
            <div className="ep-card p-5">
              <div className="label-overline mb-3">Recommended Next Steps</div>
              <NextSteps aiA={aiA} aiB={aiB} cat={cat} />
            </div>
            <div className="ep-card p-5 lg:col-span-2">
              <div className="label-overline mb-3">Escalation Readiness Checklist</div>
              <EscalationChecklist context={c.context} files={c.files} layers={meta.layers} score={score} />
            </div>
          </div>
        )}

        {tab === "export" && (
          <div data-testid="tab-content-export" className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ExportCard icon={FileText} label="Markdown" desc="Human-readable report ready for handoff in chat or email." href={apiClient.exportUrl(id, "markdown")} />
            <ExportCard icon={Code} label="JSON" desc="Machine-readable structured payload for ticket systems." href={apiClient.exportUrl(id, "json")} />
            <ExportCard icon={Browsers} label="HTML (printable)" desc="Open in a new tab; print to PDF for archival." href={apiClient.exportUrl(id, "html")} />
            <div className="ep-card p-5 md:col-span-3">
              <div className="label-overline mb-2">Packaging guidance</div>
              <div className="font-mono text-sm text-[#A1A1AA]">
                {`// Zip evidence by layer:\n  /Browser /Web-tier /Portal /Server /Data-Store /Pro-client /OS-system\n// Always include the 5-line narrative: what broke / when / what changed / repro steps / what is already ruled out.`}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, bar, accent = "#fff" }) {
  return (
    <div className="px-6 py-5 border-r border-white/10 last:border-r-0">
      <div className="label-overline">{label}</div>
      <div className="font-heading font-black text-2xl mt-1" style={{ color: accent }}>{value}</div>
      {bar && <div className="mt-3">{bar}</div>}
    </div>
  );
}

function ContextDisplay({ context }) {
  const fields = [
    ["timestamps", "Timestamps + TZ"],
    ["urls", "URLs"],
    ["versions", "Versions"],
    ["topology", "Topology"],
    ["recent_changes", "Recent changes"],
    ["repro_steps", "Repro steps"],
  ];
  return (
    <div className="ep-card p-5">
      <div className="label-overline mb-3">Captured Context</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        {fields.map(([k, l]) => (
          <div key={k}>
            <div className="text-[11px] text-[#71717A] font-mono uppercase tracking-widest">{l}</div>
            <div className={`font-mono text-[12.5px] mt-0.5 ${context?.[k] ? "text-[#A1A1AA]" : "text-[#EF4444]"}`}>{context?.[k] || "(MISSING)"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DisagreementPanel({ d }) {
  return (
    <div className="ep-card p-5" data-testid="disagreement-panel">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="label-overline">Disagreement Diff</div>
          <div className="font-heading font-bold text-sm mt-0.5">A vs B comparison</div>
        </div>
        <span className={`tag ${d.layer_agreement ? "confidence-high" : "confidence-medium"}`}>
          {d.layer_agreement ? "Layer agreement" : "Layer mismatch"} · A:{d.layer_a} / B:{d.layer_b}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <div>
          <div className="label-overline mb-2">Only in A</div>
          {d.only_in_a?.length === 0 ? <div className="text-[#71717A] text-xs">(none)</div> : d.only_in_a.map((h) => <div key={`a-${h}`} className="diff-add mb-1">{h}</div>)}
        </div>
        <div>
          <div className="label-overline mb-2">Only in B</div>
          {d.only_in_b?.length === 0 ? <div className="text-[#71717A] text-xs">(none)</div> : d.only_in_b.map((h) => <div key={`b-${h}`} className="diff-add mb-1">{h}</div>)}
        </div>
      </div>
      <div className="mt-3 text-xs text-[#71717A] font-mono">{`// confidence delta: ${d.confidence_delta} (A=${d.confidence_a}, B=${d.confidence_b})`}</div>
    </div>
  );
}

function NextSteps({ aiA, aiB, cat }) {
  const steps = new Set();
  (aiA?.output?.next_collection_steps || []).forEach(s => steps.add(s));
  (aiB?.output?.next_collection_steps || []).forEach(s => steps.add(s));
  if (steps.size === 0 && cat) cat.collect_first.forEach(s => steps.add(`Collect: ${s}`));
  if (steps.size === 0) return <div className="text-sm text-[#71717A]">Run AI or pick a category.</div>;
  return (
    <ol className="text-sm text-[#A1A1AA] space-y-2 list-decimal list-inside">
      {[...steps].map((s) => <li key={s}>{s}</li>)}
    </ol>
  );
}

function EscalationChecklist({ context, files, layers, score }) {
  const items = [
    ["Timestamps with timezone", !!context?.timestamps],
    ["Reproduction steps", !!context?.repro_steps],
    ["Software versions", !!context?.versions],
    ["Deployment topology", !!context?.topology],
    ["Recent changes documented", !!context?.recent_changes],
    ["Exact URLs", !!context?.urls],
    ["At least one log file uploaded", (files || []).length > 0],
    ["Expected layer evidence covered", (score.missing_layers || []).length === 0],
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
      {items.map(([label, ok]) => (
        <div key={label} className="flex items-center gap-2 text-sm">
          <span className={`w-4 h-4 inline-flex items-center justify-center border ${ok ? "border-[#10B981] bg-[#10B981]/20 text-[#10B981]" : "border-white/20 text-[#71717A]"}`}>
            {ok ? "✓" : ""}
          </span>
          <span className={ok ? "text-white" : "text-[#71717A]"}>{label}</span>
        </div>
      ))}
    </div>
  );
}

function ExportCard({ icon: Icon, label, desc, href }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="ep-card ep-card-hover p-5 block" data-testid={`export-${label.replace(/\s+/g,"-").toLowerCase()}`}>
      <div className="flex items-center justify-between mb-3">
        <Icon size={28} weight="duotone" className="text-[#00E5FF]" />
        <Download size={16} className="text-[#71717A]" />
      </div>
      <div className="font-heading font-bold uppercase tracking-wider text-sm">{label}</div>
      <div className="text-xs text-[#A1A1AA] mt-2">{desc}</div>
    </a>
  );
}
