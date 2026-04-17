import React from "react";
import { PageHeader } from "../components/UIBits";

export default function Help() {
  return (
    <div data-testid="help-page">
      <PageHeader
        overline="Documentation"
        title="Help & Setup"
        subtitle="Quickstart, Windows VM hosting, security notes, and known limitations. The full README ships in /README.md at the repo root."
      />
      <div className="px-8 py-8 max-w-4xl space-y-6 text-sm text-[#A1A1AA] leading-relaxed">
        <Section title="Quickstart">
          <ol className="list-decimal list-inside space-y-1">
            <li>Open <code className="font-mono text-[#00E5FF]">Dashboard → New Analysis</code></li>
            <li>Pick the issue category and confirm symptom clues</li>
            <li>Capture context: <strong>timestamps + timezone, URLs, versions, topology, recent changes, repro steps</strong></li>
            <li>Inside the Case Workspace, drop log files into the uploader</li>
            <li>Run the <strong>Logic Tree</strong> tab for guided triage questions</li>
            <li>Click <strong>Run dual-AI</strong> to get side-by-side analysis</li>
            <li>Review gaps, then export Markdown / JSON / HTML for handoff</li>
          </ol>
        </Section>

        <Section title="Windows VM deployment (summary)">
          <p>
            See <code className="font-mono">/README.md</code> for the full step-by-step. Short version:
          </p>
          <ul className="list-disc list-inside space-y-1 mt-2">
            <li>Install Python 3.11+, Node 20+, MongoDB 6+, and Yarn on a Windows Server VM.</li>
            <li>Backend (<code>/backend</code>): <code className="font-mono">pip install -r requirements.txt</code> → run as a Windows service via NSSM pointing at <code>uvicorn server:app --host 0.0.0.0 --port 8001</code>.</li>
            <li>Frontend (<code>/frontend</code>): <code>yarn install &amp;&amp; yarn build</code>, serve the build folder with IIS or <code>serve -s build -l 3000</code>, also wrapped in NSSM.</li>
            <li>Configure IIS reverse-proxy: route <code>/api/*</code> to backend port and everything else to frontend.</li>
            <li>Open Windows Firewall for inbound 80/443; grant the service account write access to the upload folder.</li>
          </ul>
        </Section>

        <Section title="Security notes">
          <ul className="list-disc list-inside space-y-1">
            <li>API keys are stored server-side only and never sent to the browser.</li>
            <li>Uploaded filenames are sanitized; zip extraction blocks path traversal.</li>
            <li>Uploaded logs may contain credentials/tokens/PII — handle accordingly. Configure retention in Settings.</li>
            <li>Local admin auth is intentionally lightweight in MVP. For production, front the app with IIS auth, AD, or SSO.</li>
          </ul>
        </Section>

        <Section title="Limitations">
          <ul className="list-disc list-inside space-y-1">
            <li>AI analysis is advisory, not authoritative.</li>
            <li>Binary formats (.dmp, .evtx) are not deeply parsed in MVP — analyze externally with WinDbg / wevtutil.</li>
            <li>Model quality scales with evidence quality; missing context = low confidence.</li>
            <li>“Microsoft / Copilot-style” adapter is configurable — wire to Azure OpenAI by setting the override key & model in Settings.</li>
            <li>Very large log bundles may need chunking (current cap ~30k chars sent to each provider).</li>
          </ul>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="ep-card p-6">
      <div className="label-overline mb-3">{title}</div>
      <div className="prose prose-invert max-w-none text-sm">{children}</div>
    </div>
  );
}
