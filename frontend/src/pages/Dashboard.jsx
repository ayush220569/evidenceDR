import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../lib/api";
import { PageHeader, ProgressBar, SegmentedMeter, EmptyState, LayerTag } from "../components/UIBits";
import { Plus, ChartBar, Folder, CheckCircle, WarningCircle, Robot, Lightning } from "@phosphor-icons/react";

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [cases, setCases] = useState([]);
  const [meta, setMeta] = useState({ categories: [], layers: {} });

  useEffect(() => {
    Promise.all([apiClient.dashboardStats(), apiClient.listCases({ limit: 8 }), apiClient.getCategories()]).then(([s, c, m]) => {
      setStats(s); setCases(c.cases); setMeta(m);
    });
  }, []);

  const catName = (id) => meta.categories?.find(c => c.id === id)?.short || id;

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        overline="Mission Control / Triage Cockpit"
        title="EvidencePilot Dashboard"
        subtitle="Smarter first-pass evidence collection and AI-assisted log triage for ArcGIS Online, Enterprise, and Pro support cases."
        right={
          <button onClick={() => navigate("/new")} className="btn-primary" data-testid="dashboard-new-analysis-btn">
            <Plus size={16} weight="bold" /> New Analysis
          </button>
        }
      />

      <div className="px-8 py-8 space-y-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-0 border border-white/10 rounded-md overflow-hidden">
          <StatCell icon={Folder} label="Total Cases" value={stats?.total ?? "—"} />
          <StatCell icon={WarningCircle} label="Open" value={stats?.open ?? "—"} accent="#F59E0B" />
          <StatCell icon={CheckCircle} label="Resolved" value={stats?.resolved ?? "—"} accent="#10B981" />
          <StatCell icon={Robot} label="AI-Analyzed" value={stats?.analyzed ?? "—"} accent="#00E5FF" />
        </div>

        {/* Avg completeness + Quick start */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="ep-card p-6 lg:col-span-2" data-testid="avg-completeness-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="label-overline">Average Evidence Completeness</div>
                <div className="font-heading text-3xl font-black mt-1">{stats?.avg_completeness ?? 0}%</div>
              </div>
              <SegmentedMeter value={stats?.avg_completeness ?? 0} segments={14} testid="avg-completeness-meter" />
            </div>
            <ProgressBar value={stats?.avg_completeness ?? 0} testid="avg-completeness-bar" />
            <p className="text-xs text-[#71717A] mt-3 font-mono">
              {"// Higher completeness = fewer back-and-forth loops with the customer"}
            </p>
          </div>
          <div className="ep-card p-6" data-testid="quickstart-card">
            <div className="label-overline mb-3">Quick Start Wizard</div>
            <div className="font-heading font-bold text-lg mb-3">Begin a guided triage</div>
            <ol className="text-sm text-[#A1A1AA] space-y-2 mb-5 font-mono text-[12.5px]">
              <li>{"01 / pick category"}</li>
              <li>{"02 / capture context"}</li>
              <li>{"03 / upload evidence"}</li>
              <li>{"04 / run dual-AI"}</li>
            </ol>
            <button className="btn-primary w-full justify-center" onClick={() => navigate("/new")} data-testid="quickstart-launch-btn">
              <Lightning size={14} weight="fill" /> Launch
            </button>
          </div>
        </div>

        {/* Recent cases */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="label-overline">Recent Cases</div>
              <div className="font-heading text-xl font-bold mt-1">Active triage queue</div>
            </div>
            <button onClick={() => navigate("/cases")} className="btn-ghost" data-testid="view-all-cases-btn">View all</button>
          </div>
          {cases.length === 0 ? (
            <EmptyState icon={ChartBar} title="No cases yet" hint="Create your first analysis to begin collecting evidence." action={
              <button className="btn-primary" onClick={() => navigate("/new")} data-testid="empty-new-case-btn"><Plus size={14} weight="bold" /> New Analysis</button>
            } />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {cases.map(c => (
                <button
                  key={c.id}
                  onClick={() => navigate(`/cases/${c.id}`)}
                  className="ep-card ep-card-hover p-5 text-left"
                  data-testid={`case-card-${c.id}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="font-heading font-bold text-base leading-tight line-clamp-2">{c.title}</div>
                    <LayerTag layer={c.score?.readiness === "high" ? "client_pro" : "unknown"} layers={{
                      client_pro: { name: c.score?.readiness?.toUpperCase() || "?", color: c.score?.readiness === "high" ? "#10B981" : c.score?.readiness === "medium" ? "#F59E0B" : "#EF4444" },
                      unknown: { name: c.score?.readiness?.toUpperCase() || "?", color: "#71717A" }
                    }} />
                  </div>
                  <div className="text-[11px] text-[#71717A] font-mono uppercase tracking-wider mb-3">{catName(c.category_id)}</div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-[#A1A1AA]">{c.score?.overall_pct ?? 0}%</span>
                    <ProgressBar value={c.score?.overall_pct ?? 0} />
                  </div>
                  <div className="flex items-center justify-between mt-3 text-[11px] text-[#71717A]">
                    <span>{(c.files || []).length} files</span>
                    <span>{c.ai_results?.ran_at ? "AI ✓" : "AI —"}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Why this matters */}
        <div className="ep-card p-6" data-testid="why-this-matters-card">
          <div className="label-overline mb-2">Why This Matters</div>
          <h3 className="font-heading font-black uppercase text-2xl mb-4">Logs alone are only half the battle.</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm text-[#A1A1AA]">
            <Reason title="First-pass accuracy" body="Capture the right artifact the first time and skip the rework loop." />
            <Reason title="Confidence under pressure" body="A scored readiness meter gives engineers a clear go / no-go signal." />
            <Reason title="Less back-and-forth" body="Context fields enforce timestamps, URLs, versions, topology, and changes." />
            <Reason title="Right layer fast" body="Category-aware rules hint at which layer (Web tier? Pro? Data Store?)." />
            <Reason title="Power-user shortcuts" body="ProcMon for path/permission, Diagnostic Monitor for hangs, dumps for crashes." />
            <Reason title="Better escalation" body="Auto-packaged evidence by layer with the mandatory 5-line narrative." />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCell({ icon: Icon, label, value, accent = "#00E5FF" }) {
  return (
    <div className="px-6 py-5 border-r border-b border-white/10 last:border-r-0">
      <div className="flex items-center justify-between">
        <div>
          <div className="label-overline">{label}</div>
          <div className="font-heading text-3xl font-black mt-1" style={{ color: accent }}>{value}</div>
        </div>
        <Icon size={28} weight="duotone" style={{ color: accent, opacity: 0.6 }} />
      </div>
    </div>
  );
}

function Reason({ title, body }) {
  return (
    <div className="border-l-2 border-[#00E5FF]/40 pl-4">
      <div className="font-heading font-bold text-sm uppercase tracking-wider text-white">{title}</div>
      <div className="text-xs mt-1 leading-relaxed">{body}</div>
    </div>
  );
}
