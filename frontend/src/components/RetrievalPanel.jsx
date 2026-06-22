import React from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";

function scoreClass(score) {
  if (score >= 0.7) return "confidence-high";
  if (score >= 0.5) return "confidence-medium";
  return "confidence-low";
}

function ChunkCard({ ch, layers, index }) {
  const layerStyle = layers?.[ch.layer]
    ? { color: layers[ch.layer].color, borderColor: layers[ch.layer].color + "55" }
    : null;
  return (
    <div
      key={`${ch.file_id || "f"}-${ch.chunk_index ?? index}`}
      className="border border-white/5 bg-[#0A0A0C] rounded px-3 py-2"
      data-testid={`retrieved-chunk-${index}`}
    >
      <div className="flex items-center gap-2 mb-1 text-[11px]">
        <span className="font-mono text-[#71717A]">{`#${index + 1}`}</span>
        <span className="font-mono text-[#00E5FF]">{ch.file_name}</span>
        <span className="font-mono text-[#A1A1AA]">ch{ch.chunk_index}</span>
        <span className={`tag ${scoreClass(ch.score || 0)}`}>{(ch.score || 0).toFixed(3)}</span>
        {ch.source && (
          <span
            className="tag"
            style={
              ch.source === "lexical"
                ? { color: "#F59E0B", borderColor: "#F59E0B55" }
                : ch.source === "hybrid"
                ? { color: "#10B981", borderColor: "#10B98155" }
                : { color: "#71717A", borderColor: "#71717A55" }
            }
            data-testid={`retrieved-chunk-source-${index}`}
          >
            {ch.source}
          </span>
        )}
        {ch.layer && layerStyle && (
          <span className="tag" style={layerStyle}>{layers[ch.layer].name || ch.layer}</span>
        )}
      </div>
      <div className="font-mono text-[11.5px] text-[#A1A1AA] whitespace-pre-wrap leading-relaxed">{ch.preview}</div>
    </div>
  );
}

export default function RetrievalPanel({ r, layers }) {
  const chunks = r?.chunks || [];
  const query = r?.query || "";
  const queryPreview = query.slice(0, 200) + (query.length > 200 ? "…" : "");

  return (
    <div className="ep-card p-5" data-testid="retrieval-panel">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="label-overline flex items-center gap-2">
            <MagnifyingGlass size={14} weight="duotone" className="text-[#00E5FF]" /> Retrieved Evidence (RAG)
          </div>
          <div className="font-heading font-bold text-sm mt-0.5">
            Top {chunks.length} chunks fed to both providers · {r?.total_chunks_in_case || 0} chunks indexed
          </div>
        </div>
        <span className="tag confidence-high">top-k={r?.top_k}</span>
      </div>
      <div className="text-[11px] text-[#71717A] font-mono mb-3">
        {"// query: "}{queryPreview}
      </div>
      {chunks.length === 0 ? (
        <div className="text-sm text-[#71717A]">(no chunks retrieved)</div>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {chunks.map((ch, i) => <ChunkCard key={`${ch.file_id || "f"}-${ch.chunk_index ?? i}`} ch={ch} layers={layers} index={i} />)}
        </div>
      )}
    </div>
  );
}
