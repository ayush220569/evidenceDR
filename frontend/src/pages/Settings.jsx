import React, { useEffect, useState } from "react";
import { apiClient } from "../lib/api";
import { PageHeader } from "../components/UIBits";
import { FloppyDisk } from "@phosphor-icons/react";

const PROVIDER_OPTIONS = {
  openai: ["gpt-5.5", "gpt-5.5-pro", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4.1"],
  anthropic: ["claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001", "claude-opus-4-5-20251101", "claude-4-sonnet-20250514"],
  gemini: ["gemini-3-flash-preview", "gemini-3.1-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash"],
};

export default function Settings() {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => { apiClient.getSettings().then(setS); }, []);

  const save = async () => {
    setSaving(true);
    try {
      // Strip masked api keys (•) so we don't overwrite stored ones
      const payload = { ...s };
      if (payload.provider_a_api_key && payload.provider_a_api_key.includes("•")) payload.provider_a_api_key = "";
      if (payload.provider_b_api_key && payload.provider_b_api_key.includes("•")) payload.provider_b_api_key = "";
      const res = await apiClient.saveSettings(payload);
      setS(res); setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  };

  if (!s) return <div className="px-8 py-10 text-[#71717A]">Loading…</div>;

  const upd = (k, v) => setS({ ...s, [k]: v });

  return (
    <div data-testid="settings-page">
      <PageHeader
        overline="Configuration"
        title="Settings"
        subtitle="Configure AI providers, override default keys, set retention, and define escalation contact. The default uses the Emergent Universal LLM Key (no setup needed)."
        right={
          <button onClick={save} disabled={saving} className="btn-primary" data-testid="save-settings-btn">
            <FloppyDisk size={14} weight="fill" /> {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
          </button>
        }
      />
      <div className="px-8 py-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ProviderConfig title="Provider A" prefix="provider_a" s={s} upd={upd} />
        <ProviderConfig title="Provider B (Microsoft / Copilot-style)" prefix="provider_b" s={s} upd={upd} />
        <div className="ep-card p-6 lg:col-span-2">
          <div className="label-overline mb-4">Retention & limits</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <Field label="File retention (days)">
              <input type="number" min="1" value={s.retention_days || 30} onChange={e => upd("retention_days", Number(e.target.value))} className="w-full px-3 py-2" data-testid="retention-input" />
            </Field>
            <Field label="Max upload size (MB)">
              <input type="number" min="1" value={s.max_upload_mb || 512} onChange={e => upd("max_upload_mb", Number(e.target.value))} className="w-full px-3 py-2" data-testid="max-upload-input" />
            </Field>
            <Field label="Escalation contact">
              <input value={s.escalation_contact || ""} onChange={e => upd("escalation_contact", e.target.value)} className="w-full px-3 py-2" data-testid="escalation-contact-input" />
            </Field>
          </div>
          <div className="text-[11px] text-[#71717A] mt-4 font-mono">
            {"// Default escalation contact seeded as corp.support.help@esri.ca — editable per deployment."}
          </div>
        </div>
        <div className="ep-card p-6 lg:col-span-2">
          <div className="label-overline mb-4">Retrieval / RAG tuning</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <Field label="Retrieval top-K">
              <input type="number" min="1" max="200" value={s.retrieval_top_k || 40} onChange={e => upd("retrieval_top_k", Number(e.target.value))} className="w-full px-3 py-2" data-testid="retrieval-top-k-input" />
            </Field>
            <Field label="Chunk size (chars)">
              <input type="number" min="100" max="4000" value={s.chunk_size_chars || 800} onChange={e => upd("chunk_size_chars", Number(e.target.value))} className="w-full px-3 py-2" data-testid="chunk-size-input" />
            </Field>
            <Field label="Chunk overlap (chars)">
              <input type="number" min="0" max="500" value={s.chunk_overlap_chars || 100} onChange={e => upd("chunk_overlap_chars", Number(e.target.value))} className="w-full px-3 py-2" data-testid="chunk-overlap-input" />
            </Field>
            <Field label="Max chunks / file">
              <input type="number" min="100" max="50000" value={s.max_chunks_per_file || 10000} onChange={e => upd("max_chunks_per_file", Number(e.target.value))} className="w-full px-3 py-2" data-testid="max-chunks-input" />
            </Field>
            <Field label="Max index bytes / file">
              <input type="number" min="100000" value={s.max_index_bytes_per_file || 10485760} onChange={e => upd("max_index_bytes_per_file", Number(e.target.value))} className="w-full px-3 py-2 font-mono text-xs" data-testid="max-index-bytes-input" />
            </Field>
            <Field label="Index read mode">
              <select value={s.index_read_mode || "tail_first"} onChange={e => upd("index_read_mode", e.target.value)} className="w-full px-3 py-2 font-mono text-xs" data-testid="index-read-mode-select">
                <option value="head">head — first N bytes (legacy)</option>
                <option value="tail_first">tail_first — 35% head + 65% tail (recommended)</option>
                <option value="windowed">windowed — 4 evenly-spaced windows</option>
              </select>
            </Field>
          </div>
          <div className="text-[11px] text-[#71717A] mt-4 font-mono">
            {"// Hybrid retrieval: semantic (fastembed/BAAI/bge-small-en-v1.5) + lexical severity filter, RRF-fused. For files > max_index_bytes, sliding-window indexing samples the tail where errors usually live."}
          </div>
        </div>
        <div className="ep-card p-6 lg:col-span-2">
          <div className="label-overline mb-2">Sensitive data warning</div>
          <p className="text-sm text-[#A1A1AA]">
            Uploaded logs may contain credentials, tokens, or PII. The app never displays API keys in masked form (••••), and stored secrets are server-side only. Audit the retention setting above to match your org policy.
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="label-overline mb-1.5">{label}</div>
      {children}
    </label>
  );
}

function ProviderConfig({ title, prefix, s, upd }) {
  const provider = s[`${prefix}_provider`];
  return (
    <div className="ep-card p-6">
      <div className="label-overline mb-3">{title}</div>
      <Field label="Display label">
        <input value={s[`${prefix}_label`] || ""} onChange={e => upd(`${prefix}_label`, e.target.value)} className="w-full px-3 py-2 mb-3" data-testid={`${prefix}-label`} />
      </Field>
      <Field label="Provider">
        <select value={provider} onChange={e => upd(`${prefix}_provider`, e.target.value)} className="w-full px-3 py-2 mb-3" data-testid={`${prefix}-provider`}>
          {Object.keys(PROVIDER_OPTIONS).map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </Field>
      <Field label="Model">
        <select value={s[`${prefix}_model`]} onChange={e => upd(`${prefix}_model`, e.target.value)} className="w-full px-3 py-2 mb-3" data-testid={`${prefix}-model`}>
          {(PROVIDER_OPTIONS[provider] || []).map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </Field>
      <Field label="API key override (leave blank to use Emergent Universal Key)">
        <input
          type="password"
          value={s[`${prefix}_api_key`] || ""}
          onChange={e => upd(`${prefix}_api_key`, e.target.value)}
          placeholder={s[`${prefix}_api_key_set`] ? "(stored — enter new to replace)" : "(using EMERGENT_LLM_KEY)"}
          className="w-full px-3 py-2 font-mono text-xs"
          data-testid={`${prefix}-key`}
        />
      </Field>
      <div className="text-[11px] text-[#71717A] mt-2 font-mono">
        {`// ${s[`${prefix}_api_key_set`] ? "custom key configured" : "using Emergent Universal Key (default)"}`}
      </div>
    </div>
  );
}
