import React from "react";

export function PageHeader({ overline, title, subtitle, right, testid }) {
  return (
    <div className="border-b border-white/10 px-8 py-7 flex items-end justify-between gap-6" data-testid={testid || "page-header"}>
      <div>
        {overline && <div className="label-overline mb-2">{overline}</div>}
        <h1 className="font-heading font-black text-3xl sm:text-4xl tracking-tighter uppercase gradient-headline">{title}</h1>
        {subtitle && <p className="text-sm text-[#A1A1AA] mt-2 max-w-2xl">{subtitle}</p>}
      </div>
      {right && <div className="flex gap-2 items-center">{right}</div>}
    </div>
  );
}

export function ProgressBar({ value, testid }) {
  const pct = Math.max(0, Math.min(100, value || 0));
  return (
    <div className="h-2 ep-progress-track rounded-sm overflow-hidden" data-testid={testid || "progress-bar"}>
      <div className={`ep-progress-bar ${pct >= 100 ? "full" : ""}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function SegmentedMeter({ value, segments = 10, testid }) {
  const filled = Math.round((value / 100) * segments);
  return (
    <div className="flex items-center" data-testid={testid || "segmented-meter"}>
      {Array.from({ length: segments }).map((_, i) => (
        // segments is a fixed-length visual meter — index is the natural and stable key here
        <span key={`seg-${segments}-${i}`} className={`ep-segment ${i < filled ? "on" : ""}`} />
      ))}
    </div>
  );
}

export function ConfidenceBadge({ level, score, testid }) {
  const lvl = (level || "").toLowerCase();
  const cls = lvl === "high" ? "confidence-high" : lvl === "medium" ? "confidence-medium" : "confidence-low";
  return (
    <span className={`tag ${cls}`} data-testid={testid || "confidence-badge"}>
      <span className="font-bold uppercase tracking-wider">{lvl || "?"}</span>
      {typeof score === "number" && <span className="opacity-80">{score}%</span>}
    </span>
  );
}

export function LayerTag({ layer, layers, testid }) {
  const meta = layers?.[layer] || { name: layer, color: "#71717A" };
  return (
    <span
      className="tag"
      style={{ borderColor: meta.color + "55", color: meta.color, background: meta.color + "12" }}
      data-testid={testid || `layer-tag-${layer}`}
    >
      {meta.name}
    </span>
  );
}

export function EmptyState({ icon: Icon, title, hint, action }) {
  return (
    <div className="border border-dashed border-white/10 rounded-md py-16 px-6 text-center">
      {Icon && <Icon size={56} weight="duotone" className="text-white/10 mx-auto mb-4" />}
      <div className="font-heading font-bold uppercase tracking-wider text-sm text-white/80">{title}</div>
      {hint && <div className="text-xs text-[#71717A] mt-2 max-w-md mx-auto">{hint}</div>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
