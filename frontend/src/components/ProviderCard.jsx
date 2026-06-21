import React from "react";
import { ConfidenceBadge } from "./UIBits";

function confidenceLevel(score) {
  if (score >= 75) return "high";
  if (score >= 50) return "medium";
  return "low";
}

function ProviderError({ label, model, error }) {
  return (
    <div className="ep-card p-5">
      <div className="label-overline mb-2">{label} — {model}</div>
      <div className="diff-rem text-sm">{error}</div>
    </div>
  );
}

function HypothesisList({ items }) {
  if (!items?.length) return null;
  return (
    <div className="mt-3">
      <div className="label-overline mb-1">Ranked hypotheses</div>
      <ul className="text-sm space-y-1.5">
        {items.map((h, i) => (
          <li key={`${h.hypothesis || "h"}-${i}`} className="flex items-start gap-2">
            <span className="font-mono text-[#71717A] text-xs mt-0.5">{`h${i + 1}`}</span>
            <div className="flex-1">
              <div className="text-[#fff]">{h.hypothesis}</div>
              <div className="text-[11px] text-[#71717A] font-mono">
                conf: {h.confidence} · supporting: {(h.supporting_evidence || []).join(", ") || "—"}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function NextStepsList({ items }) {
  if (!items?.length) return null;
  return (
    <div className="mt-3">
      <div className="label-overline mb-1">Next collection steps</div>
      <ol className="text-sm text-[#A1A1AA] space-y-1 list-decimal list-inside">
        {items.map((s, i) => <li key={`${s.slice(0, 40)}-${i}`}>{s}</li>)}
      </ol>
    </div>
  );
}

function TerminalBlock({ overline, text }) {
  if (!text) return null;
  return (
    <div className="mt-3">
      <div className="label-overline mb-1">{overline}</div>
      <div className="terminal-block">{text}</div>
    </div>
  );
}

export default function ProviderCard({ label, data }) {
  if (!data) return <div className="ep-card p-5 text-sm text-[#71717A]">{label}: not run</div>;
  if (data.error) return <ProviderError label={label} model={data.model} error={data.error} />;

  const out = data.output || {};
  const conf = out.confidence_score || 0;
  const testid = `provider-card-${label.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <div className="ep-card p-5" data-testid={testid}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="label-overline">{label}</div>
          <div className="font-heading font-bold text-sm mt-0.5">{data.provider_label}</div>
          <div className="text-[11px] text-[#71717A] font-mono">{data.model}</div>
        </div>
        <ConfidenceBadge level={confidenceLevel(conf)} score={conf} />
      </div>
      <div className="text-sm text-[#A1A1AA] mb-3">{out.triage_summary || "(no summary)"}</div>
      <div className="text-xs">
        <div className="label-overline mb-1">Likely layer</div>
        <span className="tag confidence-high">{out.likely_layer || "?"}</span>
      </div>
      <HypothesisList items={out.ranked_hypotheses} />
      <NextStepsList items={out.next_collection_steps} />
      <TerminalBlock overline="Customer-facing draft" text={out.customer_summary} />
      <TerminalBlock overline="Internal escalation" text={out.internal_escalation_summary} />
    </div>
  );
}
