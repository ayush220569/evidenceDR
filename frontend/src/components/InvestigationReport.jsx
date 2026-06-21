import React from "react";
import { ConfidenceBadge, EmptyState } from "./UIBits";
import { Detective, Clock, Lightbulb, Target, ListChecks, Warning, Brain } from "@phosphor-icons/react";

const CONF_LEVELS = new Set(["low", "medium", "high"]);

function asLevel(v) {
  const s = (v || "").toLowerCase();
  return CONF_LEVELS.has(s) ? s : "low";
}

function Section({ icon: Icon, title, accent = "#00E5FF", children, testid }) {
  return (
    <section className="ep-card p-6" data-testid={testid}>
      <div className="flex items-center gap-2 mb-3">
        <Icon size={18} weight="duotone" style={{ color: accent }} />
        <div className="label-overline" style={{ color: accent }}>{title}</div>
      </div>
      {children}
    </section>
  );
}

function EvidenceList({ items }) {
  if (!items?.length) return null;
  return (
    <ul className="mt-2 space-y-1">
      {items.map((ev, j) => (
        <li key={`${ev}-${j}`} className="font-mono text-[11.5px] text-[#71717A] leading-relaxed">
          {"› "}{ev}
        </li>
      ))}
    </ul>
  );
}

export default function InvestigationReport({ orch }) {
  if (!orch || orch.status === "idle") {
    return null;
  }
  if (orch.status === "running") {
    const phaseNames = ["plan", "map", "reduce", "critique", "memory"];
    const done = new Set(orch.phases || []);
    return (
      <div className="ep-card p-8 text-center" data-testid="investigation-running">
        <Detective size={48} weight="duotone" className="mx-auto mb-4 text-[#00E5FF] animate-pulse" />
        <div className="font-heading font-black uppercase tracking-tight text-xl mb-1">Investigation in progress…</div>
        <div className="text-sm text-[#A1A1AA] mb-6">Map-reduce + self-critique over the indexed evidence corpus.</div>
        <div className="flex items-center justify-center gap-3 font-mono text-xs uppercase tracking-widest">
          {phaseNames.map((p, i) => {
            const isDone = done.has(p);
            const isActive = !isDone && i === done.size;
            return (
              <React.Fragment key={p}>
                <span className={`px-3 py-1.5 border ${isDone ? "border-[#10B981] text-[#10B981]" : isActive ? "border-[#00E5FF] text-[#00E5FF] animate-pulse" : "border-white/10 text-[#71717A]"}`}>
                  {p}
                </span>
                {i < phaseNames.length - 1 && <div className="w-4 h-px bg-white/10" />}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    );
  }
  if (orch.status === "error") {
    return <div className="ep-card p-6 diff-rem">Orchestrator error: {orch.error || "unknown"}</div>;
  }
  if (orch.status === "no_evidence") {
    return <EmptyState icon={Detective} title="No evidence to investigate" hint="Upload some log files first, then re-run the orchestrator." />;
  }
  if (orch.status === "reduce_failed") {
    return <div className="ep-card p-6 diff-rem">Synthesis phase failed: {orch.draft_error || "unknown"}. Try again or fall back to the fast dual-AI mode.</div>;
  }

  const r = orch.report || {};
  if (!r || Object.keys(r).length === 0) return null;

  const stats = orch.stats || {};
  const rc = r.root_cause || {};

  return (
    <div className="space-y-4" data-testid="investigation-report">
      {/* Header / stats strip */}
      <div className="ep-card p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="label-overline">Investigation Report</div>
          <div className="font-heading font-black text-2xl mt-1 uppercase tracking-tight gradient-headline">Deep Triage Complete</div>
          <div className="text-[11px] text-[#71717A] font-mono mt-1">
            {orch.model} · phases: {(orch.phases || []).join(" → ")}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="tag">{stats.map_batches || 0} batches</span>
          <span className="tag">{stats.chunks_mapped || 0} chunks analyzed</span>
          <span className="tag">{stats.priors_used || 0} prior cases</span>
          <ConfidenceBadge level={asLevel(rc.confidence)} />
        </div>
      </div>

      {/* Overview */}
      <Section icon={Brain} title="Overview" testid="report-overview">
        <p className="text-sm text-[#fff] leading-relaxed">{r.overview || "(no overview)"}</p>
        {r.likely_layer && (
          <div className="mt-3 text-xs">
            <span className="text-[#71717A] mr-2">Likely layer:</span>
            <span className="tag confidence-high">{r.likely_layer}</span>
          </div>
        )}
      </Section>

      {/* Key findings */}
      <Section icon={Lightbulb} title="Key Findings" accent="#F59E0B" testid="report-findings">
        {r.key_findings?.length ? (
          <ul className="space-y-3">
            {r.key_findings.map((f, i) => (
              <li key={`${(f.finding || "f").slice(0, 40)}-${i}`} className="border-l-2 pl-3" style={{ borderColor: f.confidence === "high" ? "#10B981" : f.confidence === "medium" ? "#F59E0B" : "#EF4444" }}>
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="text-sm text-white">{f.finding}</div>
                  <ConfidenceBadge level={asLevel(f.confidence)} />
                </div>
                <EvidenceList items={f.evidence} />
              </li>
            ))}
          </ul>
        ) : <div className="text-sm text-[#71717A]">(none)</div>}
      </Section>

      {/* Timeline */}
      <Section icon={Clock} title="Timeline of Events" accent="#7C3AED" testid="report-timeline">
        {r.timeline?.length ? (
          <ol className="relative border-l-2 border-white/10 pl-4 space-y-3">
            {r.timeline.map((t, i) => (
              <li key={`${t.ts || "t"}-${i}`} className="relative">
                <span className="absolute -left-[21px] top-1 w-2 h-2 bg-[#7C3AED] rounded-full" />
                <div className="font-mono text-[11px] text-[#7C3AED] uppercase tracking-widest">{t.ts || "?"}</div>
                <div className="text-sm text-white mt-0.5">{t.event}</div>
                {t.evidence_ref && <div className="text-[11px] text-[#71717A] font-mono mt-0.5">{"› "}{t.evidence_ref}</div>}
              </li>
            ))}
          </ol>
        ) : <div className="text-sm text-[#71717A]">(no chronology reconstructed)</div>}
      </Section>

      {/* Root cause */}
      <Section icon={Target} title="Root Cause Analysis" accent="#EF4444" testid="report-rootcause">
        {rc.primary_hypothesis ? (
          <>
            <div className="font-heading font-bold text-base text-white mb-1">{rc.primary_hypothesis}</div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] text-[#71717A]">Confidence:</span>
              <ConfidenceBadge level={asLevel(rc.confidence)} />
            </div>
            {rc.supporting_evidence?.length > 0 && (
              <>
                <div className="label-overline mb-1">Supporting evidence</div>
                <EvidenceList items={rc.supporting_evidence} />
              </>
            )}
            {rc.alternative_hypotheses?.length > 0 && (
              <div className="mt-3">
                <div className="label-overline mb-1">Alternative hypotheses</div>
                <ul className="text-sm text-[#A1A1AA] list-disc list-inside space-y-0.5">
                  {rc.alternative_hypotheses.map((h, i) => <li key={`alt-${i}-${(h || "").slice(0, 20)}`}>{h}</li>)}
                </ul>
              </div>
            )}
          </>
        ) : <div className="text-sm text-[#71717A]">(root cause not determined)</div>}
      </Section>

      {/* Recommendations */}
      <Section icon={ListChecks} title="Recommendations / Next Steps" accent="#10B981" testid="report-recommendations">
        {r.recommendations?.length ? (
          <ol className="text-sm text-white space-y-2 list-decimal list-inside">
            {r.recommendations.map((s, i) => <li key={`${s.slice(0, 30)}-${i}`}>{s}</li>)}
          </ol>
        ) : <div className="text-sm text-[#71717A]">(none)</div>}
      </Section>

      {/* Gaps */}
      {r.gaps?.length > 0 && (
        <Section icon={Warning} title="Evidence Gaps" accent="#FF9F1C" testid="report-gaps">
          <ul className="text-sm text-[#A1A1AA] list-disc list-inside space-y-1">
            {r.gaps.map((g, i) => <li key={`gap-${i}-${(g || "").slice(0, 20)}`}>{g}</li>)}
          </ul>
        </Section>
      )}

      {/* Revisions */}
      {r.revisions?.length > 0 && (
        <Section icon={Brain} title="Critique Revisions" accent="#A1A1AA" testid="report-revisions">
          <ul className="text-[12px] text-[#71717A] font-mono list-disc list-inside space-y-1">
            {r.revisions.map((rv, i) => <li key={`rv-${i}-${(rv || "").slice(0, 24)}`}>{rv}</li>)}
          </ul>
        </Section>
      )}
    </div>
  );
}
