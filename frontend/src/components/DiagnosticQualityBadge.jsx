import React, { useEffect, useState } from "react";
import { apiClient } from "../lib/api";
import { ShieldCheck, Database, MagnifyingGlassPlus, ChartLineUp } from "@phosphor-icons/react";

const GRADE_COLOR = {
  high: { text: "#10B981", border: "#10B98155", bg: "#10B98112" },
  medium: { text: "#F59E0B", border: "#F59E0B55", bg: "#F59E0B12" },
  low: { text: "#EF4444", border: "#EF444455", bg: "#EF444412" },
};

function Stat({ label, value, hint, testId }) {
  return (
    <div className="border border-white/5 rounded px-3 py-2 bg-[#0A0A0C]" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider text-[#71717A] font-mono">{label}</div>
      <div className="text-sm font-mono text-white mt-0.5">{value}</div>
      {hint && <div className="text-[10px] text-[#71717A] mt-0.5">{hint}</div>}
    </div>
  );
}

export default function DiagnosticQualityBadge({ caseId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const d = await apiClient.diagnosticQuality(caseId);
        if (!cancelled) setData(d);
      } catch (e) {
        if (!cancelled) setErr(e.response?.data?.detail || e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [caseId]);

  if (loading) {
    return (
      <div className="ep-card p-4" data-testid="diagnostic-quality-loading">
        <div className="text-[11px] font-mono text-[#71717A]">Computing diagnostic quality…</div>
      </div>
    );
  }
  if (err) {
    return <div className="ep-card p-4 text-[11px] text-[#EF4444] font-mono" data-testid="diagnostic-quality-error">Quality probe failed: {err}</div>;
  }
  if (!data) return null;

  const grade = data.grade || "low";
  const c = GRADE_COLOR[grade] || GRADE_COLOR.low;
  const pct = Math.round((data.quality_score || 0) * 100);
  const lex = data.retrieval_sources?.lexical || 0;
  const sem = data.retrieval_sources?.semantic || 0;
  const hyb = data.retrieval_sources?.hybrid || 0;
  const ref = data.benchmark_reference || {};

  return (
    <div
      className="ep-card p-4"
      style={{ borderColor: c.border, background: c.bg }}
      data-testid="diagnostic-quality-badge"
    >
      <div className="flex items-center gap-3 mb-3">
        <ShieldCheck size={28} weight="duotone" style={{ color: c.text }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <div className="font-heading font-bold uppercase tracking-wider text-sm">Diagnostic Quality</div>
            <span className="tag" style={{ color: c.text, borderColor: c.border }} data-testid="quality-grade">{grade}</span>
          </div>
          <div className="text-[11px] text-[#71717A] font-mono mt-0.5">
            Composite score · indexing coverage + severity recall + LLM confidence
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-heading font-bold" style={{ color: c.text }} data-testid="quality-score">{pct}<span className="text-sm text-[#71717A]">/100</span></div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-3">
        <Stat
          label="Index coverage"
          value={`${Math.round((data.coverage || 0) * 100)}%`}
          hint={`${data.indexed_files}/${data.total_files} files · ${data.indexed_chunks_total.toLocaleString()} chunks`}
          testId="quality-stat-coverage"
        />
        <Stat
          label="Severity chunks"
          value={data.severity_chunks_retrieved}
          hint="surfaced by lexical branch"
          testId="quality-stat-severity"
        />
        <Stat
          label="Retrieval mix"
          value={`L${lex} · H${hyb} · S${sem}`}
          hint="lexical / hybrid / semantic"
          testId="quality-stat-retrieval"
        />
        <Stat
          label="LLM confidence"
          value={data.confidence_overall || "—"}
          hint={data.orchestrator_status === "done" ? "from orchestrator" : `status: ${data.orchestrator_status || "not run"}`}
          testId="quality-stat-confidence"
        />
      </div>

      <details className="border-t border-white/5 pt-3 mt-1" data-testid="quality-benchmark-details">
        <summary className="text-[11px] font-mono text-[#71717A] cursor-pointer hover:text-white flex items-center gap-1">
          <ChartLineUp size={12} weight="duotone" />
          Hybrid retrieval impact (benchmark reference)
        </summary>
        <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono">
          <div className="border border-white/5 rounded p-2 bg-[#0A0A0C]">
            <div className="flex items-center gap-1 text-[#EF4444]"><MagnifyingGlassPlus size={12} /> Before (semantic-only)</div>
            <div className="text-[#A1A1AA] mt-1">1 MB SAML case · needle rank: <span className="text-[#EF4444]">{ref.semantic_only_1mb_needle_rank || "?"}</span></div>
            <div className="text-[#A1A1AA]">noise floor ≈ {ref.noise_floor_score || "?"}</div>
          </div>
          <div className="border border-white/5 rounded p-2 bg-[#0A0A0C]">
            <div className="flex items-center gap-1 text-[#10B981]"><Database size={12} /> After (hybrid + RRF)</div>
            <div className="text-[#A1A1AA] mt-1">needle at <span className="text-[#10B981]">rank {ref.hybrid_1mb_needle_rank}</span> · score {ref.hybrid_1mb_needle_score}</div>
            <div className="text-[#A1A1AA]">orchestrator cites verbatim ERROR lines</div>
          </div>
        </div>
        <div className="text-[10px] text-[#71717A] mt-2">
          Caps · max_chunks={data.caps.max_chunks_per_file.toLocaleString()} · chunk={data.caps.chunk_size_chars} chars ·
          max_bytes={(data.caps.max_index_bytes_per_file / 1_000_000).toFixed(0)} MB
        </div>
      </details>
    </div>
  );
}
