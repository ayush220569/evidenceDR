import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../lib/api";
import { PageHeader, ProgressBar, EmptyState } from "../components/UIBits";
import { Folders, Plus, Trash } from "@phosphor-icons/react";

export default function CasesList() {
  const nav = useNavigate();
  const [cases, setCases] = useState([]);
  const [meta, setMeta] = useState({ categories: [] });
  const [filter, setFilter] = useState("all");

  const load = () => apiClient.listCases({ limit: 200 }).then(d => setCases(d.cases));
  useEffect(() => { load(); apiClient.getCategories().then(setMeta); }, []);

  const filtered = cases.filter(c => filter === "all" || c.status === filter);
  const catName = (id) => meta.categories?.find(c => c.id === id)?.short || id;

  const remove = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this case and its files?")) return;
    await apiClient.deleteCase(id);
    load();
  };

  return (
    <div data-testid="cases-list-page">
      <PageHeader
        overline="Case Archive"
        title="All Cases"
        right={<button onClick={() => nav("/new")} className="btn-primary" data-testid="cases-new-btn"><Plus size={14} weight="bold" /> New</button>}
      />
      <div className="px-8 py-6">
        <div className="flex gap-2 mb-6 font-mono text-xs uppercase tracking-widest">
          {["all", "open", "resolved"].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 border ${filter === f ? "border-[#00E5FF] text-[#00E5FF]" : "border-white/10 text-[#71717A] hover:text-white"}`}
              data-testid={`filter-${f}`}
            >{f}</button>
          ))}
        </div>
        {filtered.length === 0 ? (
          <EmptyState icon={Folders} title="No cases" hint="Click 'New' to begin." />
        ) : (
          <div className="border border-white/10 rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#121215] border-b border-white/10 font-mono text-[11px] uppercase tracking-widest text-[#71717A]">
                <tr>
                  <th className="text-left px-4 py-3">Title</th>
                  <th className="text-left px-4 py-3">Category</th>
                  <th className="text-left px-4 py-3">Files</th>
                  <th className="text-left px-4 py-3 w-48">Completeness</th>
                  <th className="text-left px-4 py-3">AI</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-right px-4 py-3 w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => (
                  <tr
                    key={c.id}
                    onClick={() => nav(`/cases/${c.id}`)}
                    className="border-b border-white/5 hover:bg-white/5 cursor-pointer"
                    data-testid={`case-row-${c.id}`}
                  >
                    <td className="px-4 py-3 font-heading font-bold">{c.title}</td>
                    <td className="px-4 py-3 text-[#A1A1AA] font-mono text-xs">{catName(c.category_id)}</td>
                    <td className="px-4 py-3 text-[#A1A1AA]">{c.files?.length || 0}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs w-9">{c.score?.overall_pct ?? 0}%</span>
                        <ProgressBar value={c.score?.overall_pct ?? 0} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-[#A1A1AA]">{c.ai_results?.ran_at ? "✓" : "—"}</td>
                    <td className="px-4 py-3"><span className="tag">{c.status}</span></td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={(e) => remove(c.id, e)} className="text-[#71717A] hover:text-[#EF4444]" data-testid={`delete-case-${c.id}`}>
                        <Trash size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
