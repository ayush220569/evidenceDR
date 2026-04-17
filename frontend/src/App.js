import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "@/components/AppShell";
import Dashboard from "@/pages/Dashboard";
import NewAnalysis from "@/pages/NewAnalysis";
import CasesList from "@/pages/CasesList";
import CaseWorkspace from "@/pages/CaseWorkspace";
import GuidanceLibrary from "@/pages/GuidanceLibrary";
import Settings from "@/pages/Settings";
import Help from "@/pages/Help";
import { Toaster } from "@/components/ui/sonner";

function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewAnalysis />} />
          <Route path="/cases" element={<CasesList />} />
          <Route path="/cases/:id" element={<CaseWorkspace />} />
          <Route path="/library" element={<GuidanceLibrary />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/help" element={<Help />} />
        </Routes>
      </AppShell>
      <Toaster theme="dark" />
    </BrowserRouter>
  );
}

export default App;
