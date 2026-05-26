import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiClient } from "../lib/api";
import { PageHeader, ProgressBar, SegmentedMeter, ConfidenceBadge, LayerTag, EmptyState } from "../components/UIBits";
import FileUploader from "../components/FileUploader";
import LogicTree from "../components/LogicTree";
import { Robot, Sparkle, Download, FileText, Code, Browsers, ArrowsClockwise, WarningCircle, CheckCircle, MagnifyingGlass } from "@phosphor-icons/react";

export default function CaseWorkspace() {
  const { id } = useParams();
  const nav = useNavigate();
  const [c, setC] = useState(null);
  const [meta, setMeta] = useState({ categories: [], layers: {} });
  const [tab, setTab] = useState("evidence");
  const [analyzing, setAnalyzing] = useState(false);

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
            <button onClick={runAI} disabled={analyzing} className="btn-primary" data-testid="run-ai-btn">
              <Robot size={14} weight="duotone" /> {analyzing ? "Analyzing…" : "Run dual-AI"}
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

function ProviderCard({ label, data }) {
  if (!data) return <div className="ep-card p-5 text-sm text-[#71717A]">{label}: not run</div>;
  if (data.error) return <div className="ep-card p-5"><div className="label-overline mb-2">{label} — {data.model}</div><div className="diff-rem text-sm">{data.error}</div></div>;
  const out = data.output || {};
  const conf = out.confidence_score || 0;
  const level = conf >= 75 ? "high" : conf >= 50 ? "medium" : "low";
  return (
    <div className="ep-card p-5" data-testid={`provider-card-${label.replace(/\s+/g, "-").toLowerCase()}`}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="label-overline">{label}</div>
          <div className="font-heading font-bold text-sm mt-0.5">{data.provider_label}</div>
          <div className="text-[11px] text-[#71717A] font-mono">{data.model}</div>
        </div>
        <ConfidenceBadge level={level} score={conf} />
      </div>
      <div className="text-sm text-[#A1A1AA] mb-3">{out.triage_summary || "(no summary)"}</div>
      <div className="text-xs">
        <div className="label-overline mb-1">Likely layer</div>
        <span className="tag confidence-high">{out.likely_layer || "?"}</span>
      </div>
      <div className="mt-3">
        <div className="label-overline mb-1">Ranked hypotheses</div>
        <ul className="text-sm space-y-1.5">
          {(out.ranked_hypotheses || []).map((h, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="font-mono text-[#71717A] text-xs mt-0.5">{`h${i+1}`}</span>
              <div className="flex-1">
                <div className="text-[#fff]">{h.hypothesis}</div>
                <div className="text-[11px] text-[#71717A] font-mono">conf: {h.confidence} · supporting: {(h.supporting_evidence||[]).join(", ") || "—"}</div>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-3">
        <div className="label-overline mb-1">Next collection steps</div>
        <ol className="text-sm text-[#A1A1AA] space-y-1 list-decimal list-inside">
          {(out.next_collection_steps || []).map((s, i) => <li key={i}>{s}</li>)}
        </ol>
      </div>
      {out.customer_summary && (
        <div className="mt-3">
          <div className="label-overline mb-1">Customer-facing draft</div>
          <div className="terminal-block">{out.customer_summary}</div>
        </div>
      )}
      {out.internal_escalation_summary && (
        <div className="mt-3">
          <div className="label-overline mb-1">Internal escalation</div>
          <div className="terminal-block">{out.internal_escalation_summary}</div>
        </div>
      )}
    </div>
  );
}

function RetrievalPanel({ r, layers }) {
  const chunks = r?.chunks || [];
  return (
    <div className="ep-card p-5" data-testid="retrieval-panel">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="label-overline flex items-center gap-2"><MagnifyingGlass size={14} weight="duotone" className="text-[#00E5FF]" /> Retrieved Evidence (RAG)</div>
          <div className="font-heading font-bold text-sm mt-0.5">Top {chunks.length} chunks fed to both providers · {r?.total_chunks_in_case || 0} chunks indexed</div>
        </div>
        <span className="tag confidence-high">top-k={r?.top_k}</span>
      </div>
      <div className="text-[11px] text-[#71717A] font-mono mb-3">
        {"// query: "}{(r?.query || "").slice(0, 200)}{(r?.query || "").length > 200 ? "…" : ""}
      </div>
      {chunks.length === 0 ? (
        <div className="text-sm text-[#71717A]">(no chunks retrieved)</div>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {chunks.map((ch, i) => (
            <div key={i} className="border border-white/5 bg-[#0A0A0C] rounded px-3 py-2" data-testid={`retrieved-chunk-${i}`}>
              <div className="flex items-center gap-2 mb-1 text-[11px]">
                <span className="font-mono text-[#71717A]">{`#${i+1}`}</span>
                <span className="font-mono text-[#00E5FF]">{ch.file_name}</span>
                <span className="font-mono text-[#A1A1AA]">ch{ch.chunk_index}</span>
                <span className={`tag ${ch.score >= 0.7 ? "confidence-high" : ch.score >= 0.5 ? "confidence-medium" : "confidence-low"}`}>{(ch.score || 0).toFixed(3)}</span>
                {ch.layer && <span className="tag" style={{ color: layers?.[ch.layer]?.color, borderColor: (layers?.[ch.layer]?.color || "#71717A") + "55" }}>{layers?.[ch.layer]?.name || ch.layer}</span>}
              </div>
              <div className="font-mono text-[11.5px] text-[#A1A1AA] whitespace-pre-wrap leading-relaxed">{ch.preview}</div>
            </div>
          ))}
        </div>
      )}
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
          {d.only_in_a?.length === 0 ? <div className="text-[#71717A] text-xs">(none)</div> : d.only_in_a.map((h, i) => <div key={i} className="diff-add mb-1">{h}</div>)}
        </div>
        <div>
          <div className="label-overline mb-2">Only in B</div>
          {d.only_in_b?.length === 0 ? <div className="text-[#71717A] text-xs">(none)</div> : d.only_in_b.map((h, i) => <div key={i} className="diff-add mb-1">{h}</div>)}
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
      {[...steps].map((s, i) => <li key={i}>{s}</li>)}
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
