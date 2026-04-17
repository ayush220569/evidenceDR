import React, { useEffect, useState } from "react";
import { apiClient } from "../lib/api";
import { PageHeader } from "../components/UIBits";
import { BookOpen, Lightbulb, Warning } from "@phosphor-icons/react";

const TIPS = [
  { t: "Hangs need Diagnostic Monitor", b: "Pure dumps are not enough for a Pro hang. Capture Diagnostic Monitor while reproducing, THEN take a process dump." },
  { t: "Path / permission errors → ProcMon", b: "Filter ProcMon to the suspect path or process. The 'ACCESS DENIED' line is your golden ticket." },
  { t: "Crashes need .dmp + Event Viewer + GPU driver + Pro build", b: "Reproduce in a clean profile (rename %appdata%\\ESRI\\ArcGISPro) to isolate user-profile corruption from product defects." },
  { t: "WebGISDR scheduled-fails-only ≈ permissions or sleep/wake", b: "If manual works but scheduled fails, the service account or sleep policy is almost always the cause." },
  { t: "Direct 7443/6443 works while Web Adaptor fails ⇒ front-door", b: "When direct ports work, the issue is in the IIS / proxy / Web Adaptor / TLS edge, NOT the back-end." },
  { t: "Always reinforce essential context", b: "Timestamps with timezone, exact URLs, software versions, deployment topology, recent changes, and reproduction steps are MANDATORY. Logs alone are only half the battle." },
];

const COMMON_MISTAKES = [
  "Pulling Server logs only when the failure path actually goes through Web Adaptor",
  "Sending dumps without GPU driver / Pro build / Event Viewer",
  "Submitting a HAR without 'Preserve log' enabled",
  "Forgetting to grab Data Store logs from BOTH primary AND standby",
  "Time-zone-less timestamps (causes hours of useless log diving)",
  "Shotgun zip uploads with no narrative — packagers can't triage what they can't structure",
];

export default function GuidanceLibrary() {
  const [meta, setMeta] = useState({ categories: [] });
  const [active, setActive] = useState(null);

  useEffect(() => {
    apiClient.getCategories().then(d => { setMeta(d); setActive(d.categories[0]?.id); });
  }, []);

  const cat = meta.categories.find(c => c.id === active);

  return (
    <div data-testid="guidance-library-page">
      <PageHeader
        overline="Knowledge Base"
        title="Evidence Guidance Library"
        subtitle="Category-by-category instructions, why each artifact matters, and the power-user tricks that separate first-pass wins from rework loops."
      />
      <div className="px-8 py-8 grid grid-cols-1 lg:grid-cols-4 gap-6">
        <aside className="lg:col-span-1">
          <div className="label-overline mb-3">Categories</div>
          <div className="space-y-1">
            {meta.categories.map(c => (
              <button
                key={c.id}
                onClick={() => setActive(c.id)}
                className={`w-full text-left px-3 py-2 text-sm border-l-2 ${active === c.id ? "border-[#00E5FF] bg-[#00E5FF]/5 text-[#00E5FF]" : "border-transparent text-[#A1A1AA] hover:text-white hover:bg-white/5"}`}
                data-testid={`lib-cat-${c.id}`}
              >
                {c.short}
              </button>
            ))}
          </div>
        </aside>

        <div className="lg:col-span-3 space-y-6">
          {cat && (
            <div className="ep-card p-6" data-testid="lib-cat-detail">
              <div className="label-overline">{cat.short}</div>
              <h2 className="font-heading font-black uppercase tracking-tighter text-2xl mt-1 mb-4">{cat.name}</h2>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Section title="Symptom Clues" items={cat.clues} />
                <Section title="Collect FIRST" items={cat.collect_first} accent="#00E5FF" />
                <Section title="Add if needed" items={cat.add_if_needed} accent="#A1A1AA" />
              </div>

              <div className="mt-5 border-t border-white/10 pt-4">
                <div className="label-overline mb-1 flex items-center gap-2"><Lightbulb size={14} weight="fill" className="text-[#FF9F1C]" /> Power-user tip</div>
                <div className="font-mono text-sm text-[#A1A1AA]">{`// ${cat.tips}`}</div>
              </div>
            </div>
          )}

          <div className="ep-card p-6">
            <div className="label-overline mb-3 flex items-center gap-2"><BookOpen size={14} weight="duotone" /> Top analyst tricks</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {TIPS.map(t => (
                <div key={t.t} className="border-l-2 border-[#00E5FF]/40 pl-4">
                  <div className="font-heading font-bold uppercase tracking-wide text-sm">{t.t}</div>
                  <div className="text-xs text-[#A1A1AA] mt-1 leading-relaxed">{t.b}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="ep-card p-6">
            <div className="label-overline mb-3 flex items-center gap-2"><Warning size={14} weight="fill" className="text-[#EF4444]" /> Common mistakes</div>
            <ul className="text-sm text-[#A1A1AA] space-y-1.5 list-disc list-inside">
              {COMMON_MISTAKES.map(m => <li key={m}>{m}</li>)}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, items, accent = "#fff" }) {
  return (
    <div>
      <div className="label-overline mb-2" style={{ color: accent }}>{title}</div>
      <ul className="text-sm text-[#A1A1AA] space-y-1 list-disc list-inside">
        {items.map(x => <li key={x}>{x}</li>)}
      </ul>
    </div>
  );
}
