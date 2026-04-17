import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { House, Compass, Folders, BookOpen, GearSix, Question, Lightning } from "@phosphor-icons/react";

const NAV = [
  { to: "/", label: "Dashboard", icon: House },
  { to: "/new", label: "New Analysis", icon: Compass },
  { to: "/cases", label: "All Cases", icon: Folders },
  { to: "/library", label: "Guidance Library", icon: BookOpen },
  { to: "/settings", label: "Settings", icon: GearSix },
  { to: "/help", label: "Help", icon: Question },
];

export default function AppShell({ children }) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex" data-testid="app-shell">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-white/10 bg-[#0A0A0C] flex flex-col" data-testid="sidebar">
        <div className="px-5 py-6 border-b border-white/10">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-3 group"
            data-testid="brand-button"
          >
            <div className="w-9 h-9 bg-[#00E5FF] flex items-center justify-center rounded-sm">
              <Lightning size={20} weight="fill" color="#000" />
            </div>
            <div className="text-left">
              <div className="font-heading font-black text-[15px] tracking-tight uppercase">EvidencePilot</div>
              <div className="font-mono text-[10px] text-[#71717A] uppercase tracking-widest">AI / v1.0</div>
            </div>
          </button>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 text-sm rounded-sm transition-colors ${
                  isActive
                    ? "bg-[#00E5FF]/10 text-[#00E5FF] border-l-2 border-[#00E5FF]"
                    : "text-[#A1A1AA] hover:text-white hover:bg-white/5 border-l-2 border-transparent"
                }`
              }
            >
              <Icon size={18} weight="duotone" />
              <span className="font-medium tracking-wide">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-white/10">
          <div className="label-overline mb-2">Mission Status</div>
          <div className="terminal-block text-[11px]">
            {"> system online"}
            {"\n"}
            {"> dual-AI ready"}
            {"\n"}
            <span className="text-[#10B981]">{"> standing by..."}</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 ep-grid-bg">{children}</main>
    </div>
  );
}
