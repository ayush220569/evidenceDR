import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../lib/api";
import { PageHeader } from "../components/UIBits";
import { ArrowRight, CheckSquare, Square } from "@phosphor-icons/react";

const CONTEXT_FIELDS = [
  { key: "summary", label: "Short symptom summary", required: false, type: "textarea", ph: "What is the user seeing?" },
  { key: "timestamps", label: "Timestamps with timezone", required: true, ph: "e.g. 2026-02-10 14:32 EST" },
  { key: "urls", label: "Exact URLs", required: true, ph: "e.g. https://gis.example.com/portal/sharing/rest/..." },
  { key: "versions", label: "Software / product versions", required: true, ph: "Pro 3.4, Enterprise 11.3, Web Adaptor 11.3" },
  { key: "topology", label: "Deployment topology", required: true, type: "textarea", ph: "1 Portal + 2 Server + 3 Datastore behind IIS reverse proxy" },
  { key: "recent_changes", label: "Recent changes (patches, certs, OS, GPU, policy)", required: true, type: "textarea", ph: "Patched cert last Tuesday; AD policy updated Friday" },
  { key: "repro_steps", label: "Reproduction steps", required: true, type: "textarea", ph: "1) Sign in via vanity URL 2) Click app 3) ..." },
  { key: "already_tested", label: "Already-tested actions", required: false, type: "textarea", ph: "Cleared cache; tried different browser; rebooted Web Adaptor" },
  { key: "environment_notes", label: "Customer environment notes", required: false, type: "textarea", ph: "Air-gapped; behind corporate proxy; SSO via Okta" },
];

export default function NewAnalysis() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState({ categories: [] });
  const [step, setStep] = useState(1);
  const [title, setTitle] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [clues, setClues] = useState([]);
  const [context, setContext] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { apiClient.getCategories().then(setMeta); }, []);

  const cat = meta.categories.find(c => c.id === categoryId);

  const toggleClue = (clue) => {
    setClues(prev => prev.includes(clue) ? prev.filter(c => c !== clue) : [...prev, clue]);
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      const c = await apiClient.createCase({
        title: title.trim() || `${cat?.short || "Case"} — ${new Date().toLocaleString()}`,
        category_id: categoryId,
        context, symptom_clues: clues,
      });
      navigate(`/cases/${c.id}`);
    } finally { setSubmitting(false); }
  };

  const missing = CONTEXT_FIELDS.filter(f => f.required && !(context[f.key] || "").trim()).map(f => f.label);

  return (
    <div data-testid="new-analysis-page">
      <PageHeader
        overline={`Step ${step} / 3`}
        title="New Analysis"
        subtitle="Choose category → capture context → create case workspace. Files & logic tree happen inside the workspace."
      />
      <div className="px-8 py-8 max-w-5xl">
        {/* Stepper */}
        <div className="flex items-center gap-2 mb-8 font-mono text-xs uppercase tracking-widest">
          {["Category", "Context", "Confirm"].map((label, i) => {
            const n = i + 1;
            const active = step === n;
            const done = step > n;
            return (
              <React.Fragment key={n}>
                <button
                  onClick={() => (n < step ? setStep(n) : null)}
                  className={`px-3 py-1.5 border ${active ? "border-[#00E5FF] text-[#00E5FF]" : done ? "border-[#10B981] text-[#10B981]" : "border-white/10 text-[#71717A]"}`}
                  data-testid={`step-${n}-btn`}
                >
                  {`0${n}`} / {label}
                </button>
                {i < 2 && <div className="w-6 h-px bg-white/10" />}
              </React.Fragment>
            );
          })}
        </div>

        {/* Step 1: Category */}
        {step === 1 && (
          <div data-testid="step-1-content">
            <div className="label-overline mb-4">Pick the issue category that best matches the symptom</div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {meta.categories.map(c => (
                <button
                  key={c.id}
                  onClick={() => setCategoryId(c.id)}
                  data-testid={`category-${c.id}`}
                  className={`text-left p-4 border ep-card-hover ${categoryId === c.id ? "border-[#00E5FF] bg-[#00E5FF]/5" : "border-white/10 bg-[#121215]"}`}
                >
                  <div className="font-heading font-bold uppercase text-sm tracking-wide mb-1">{c.short}</div>
                  <div className="text-[11px] text-[#71717A] line-clamp-2 font-mono">{c.name}</div>
                </button>
              ))}
            </div>

            {cat && (
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="ep-card p-4">
                  <div className="label-overline mb-2">Symptom clues for this category</div>
                  <div className="space-y-2">
                    {cat.clues.map(cl => (
                      <button key={cl} onClick={() => toggleClue(cl)} className="flex items-start gap-2 text-sm text-[#A1A1AA] hover:text-white w-full text-left" data-testid={`clue-${cl}`}>
                        {clues.includes(cl) ? <CheckSquare size={18} weight="fill" color="#00E5FF" /> : <Square size={18} />}
                        <span>{cl}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="ep-card p-4">
                  <div className="label-overline mb-2">Collect first</div>
                  <ul className="text-sm text-[#A1A1AA] space-y-1 mb-3 list-disc list-inside">
                    {cat.collect_first.map(x => <li key={x}>{x}</li>)}
                  </ul>
                  <div className="label-overline mb-2 mt-4">Add if needed</div>
                  <ul className="text-sm text-[#71717A] space-y-1 list-disc list-inside">
                    {cat.add_if_needed.map(x => <li key={x}>{x}</li>)}
                  </ul>
                  <div className="border-t border-white/10 mt-4 pt-3 text-xs text-[#A1A1AA] font-mono">
                    {"// "}{cat.tips}
                  </div>
                </div>
              </div>
            )}

            <div className="flex justify-end mt-8">
              <button disabled={!categoryId} onClick={() => setStep(2)} className="btn-primary" data-testid="to-step-2-btn">
                Continue <ArrowRight size={14} weight="bold" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Context */}
        {step === 2 && (
          <div data-testid="step-2-content">
            <div className="label-overline mb-3">Case Title</div>
            <input value={title} onChange={e => setTitle(e.target.value)} placeholder={`${cat?.short} — short descriptive title`} className="w-full px-3 py-2.5 mb-6" data-testid="case-title-input" />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {CONTEXT_FIELDS.map(f => (
                <div key={f.key} className={f.type === "textarea" ? "md:col-span-2" : ""}>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="label-overline">{f.label} {f.required && <span className="text-[#FF9F1C]">*</span>}</label>
                  </div>
                  {f.type === "textarea" ? (
                    <textarea
                      value={context[f.key] || ""}
                      onChange={e => setContext({ ...context, [f.key]: e.target.value })}
                      placeholder={f.ph} rows={3} className="w-full px-3 py-2 font-mono text-sm"
                      data-testid={`ctx-${f.key}`}
                    />
                  ) : (
                    <input
                      value={context[f.key] || ""}
                      onChange={e => setContext({ ...context, [f.key]: e.target.value })}
                      placeholder={f.ph} className="w-full px-3 py-2 font-mono text-sm"
                      data-testid={`ctx-${f.key}`}
                    />
                  )}
                </div>
              ))}
            </div>

            {missing.length > 0 && (
              <div className="diff-rem mt-6 text-sm" data-testid="missing-warning">
                <div className="font-heading font-bold uppercase tracking-wider text-xs text-[#EF4444] mb-1">Missing critical context</div>
                <div className="text-[#A1A1AA] text-xs">{missing.join(" • ")}</div>
                <div className="text-[10px] text-[#71717A] mt-1 font-mono">{"// You can still proceed, but evidence completeness will be low."}</div>
              </div>
            )}

            <div className="flex justify-between mt-8">
              <button onClick={() => setStep(1)} className="btn-ghost" data-testid="back-step-1-btn">Back</button>
              <button onClick={() => setStep(3)} className="btn-primary" data-testid="to-step-3-btn">Continue <ArrowRight size={14} weight="bold" /></button>
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {step === 3 && (
          <div data-testid="step-3-content" className="space-y-5">
            <div className="ep-card p-5">
              <div className="label-overline mb-2">Review</div>
              <div className="font-heading font-black text-2xl">{title || `${cat?.short} — ${new Date().toLocaleString()}`}</div>
              <div className="text-sm text-[#A1A1AA] mt-1 font-mono">{cat?.name}</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-5 text-sm">
                {CONTEXT_FIELDS.map(f => (
                  <div key={f.key}>
                    <div className="label-overline">{f.label}</div>
                    <div className="text-[#A1A1AA] mt-0.5 break-words font-mono text-xs">{(context[f.key] || "—")}</div>
                  </div>
                ))}
              </div>
              {clues.length > 0 && (
                <div className="mt-4">
                  <div className="label-overline mb-1">Symptom clues</div>
                  <div className="flex flex-wrap gap-2">{clues.map(c => <span key={c} className="tag">{c}</span>)}</div>
                </div>
              )}
            </div>
            <div className="flex justify-between">
              <button onClick={() => setStep(2)} className="btn-ghost" data-testid="back-step-2-btn">Back</button>
              <button onClick={submit} disabled={submitting} className="btn-primary" data-testid="create-case-btn">
                {submitting ? "Creating…" : "Create case & open workspace"} <ArrowRight size={14} weight="bold" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
