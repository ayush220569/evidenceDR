import React, { useEffect, useState } from "react";
import { apiClient } from "../lib/api";
import { CheckCircle, ArrowRight } from "@phosphor-icons/react";

export default function LogicTree({ caseId, categoryId, initial, onSaved }) {
  const [tree, setTree] = useState([]);
  const [answers, setAnswers] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!categoryId) return;
    apiClient.getLogicTree(categoryId).then(d => setTree(d.tree || []));
    if (initial?.length) {
      const map = {};
      initial.forEach(a => { map[a.node_id] = { value: a.answer_value, label: a.answer_label }; });
      setAnswers(map);
    }
  }, [categoryId, initial]);

  const allAnswered = tree.length > 0 && tree.every(n => answers[n.id]);

  const save = async () => {
    setSaving(true);
    try {
      const payload = tree.filter(n => answers[n.id]).map(n => ({
        node_id: n.id,
        question: n.q,
        answer_value: answers[n.id].value,
        answer_label: answers[n.id].label,
      }));
      const c = await apiClient.saveLogic(caseId, payload);
      onSaved?.(c);
    } finally { setSaving(false); }
  };

  return (
    <div data-testid="logic-tree">
      <div className="terminal-block !max-h-none mb-4">
        <div className="text-[#00E5FF]">{`> evidencepilot://logic-tree --category=${categoryId}`}</div>
        <div>{`> initializing decision flow...`}</div>
        <div className="text-[#71717A]">{`> ${tree.length} questions queued`}</div>
      </div>
      <div className="space-y-3">
        {tree.map((n, idx) => {
          const ans = answers[n.id];
          return (
            <div key={n.id} className={`border ${ans ? "border-[#10B981]/40" : "border-white/10"} bg-[#121215] p-4 rounded-md`} data-testid={`logic-q-${n.id}`}>
              <div className="flex items-start gap-3">
                <div className={`font-mono text-xs uppercase tracking-widest mt-0.5 ${ans ? "text-[#10B981]" : "text-[#71717A]"}`}>{`q${String(idx+1).padStart(2,"0")}`}</div>
                <div className="flex-1">
                  <div className="font-heading font-bold text-base mb-3">{n.q}</div>
                  <div className="flex flex-wrap gap-2">
                    {n.opts.map(opt => {
                      const selected = ans?.value === opt.value;
                      return (
                        <button
                          key={opt.value}
                          onClick={() => setAnswers({ ...answers, [n.id]: { value: opt.value, label: opt.label } })}
                          className={`px-3 py-1.5 text-xs border font-mono uppercase tracking-wider transition-colors ${selected ? "border-[#00E5FF] bg-[#00E5FF]/10 text-[#00E5FF]" : "border-white/15 text-[#A1A1AA] hover:text-white hover:border-white/40"}`}
                          data-testid={`logic-opt-${n.id}-${opt.value}`}
                        >
                          {selected && <CheckCircle size={12} weight="fill" className="inline mr-1" />}
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-end mt-4">
        <button onClick={save} disabled={saving || Object.keys(answers).length === 0} className="btn-primary" data-testid="save-logic-btn">
          {saving ? "Saving…" : allAnswered ? "Save logic path" : "Save partial path"} <ArrowRight size={14} weight="bold" />
        </button>
      </div>
    </div>
  );
}
