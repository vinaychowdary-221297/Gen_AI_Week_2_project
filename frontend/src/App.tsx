import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import TopNav from "./components/TopNav";
import Dashboard from "./pages/Dashboard";
import AdjusterPage from "./pages/AdjusterPage";
import ClaimsPage from "./pages/ClaimsPage";
import DocumentsPage from "./pages/DocumentsPage";
import EvaluationPage from "./pages/EvaluationPage";
import { InvestigationProvider } from "./hooks/useInvestigation";
import { api } from "./lib/api";
import type { HealthStatus } from "./types";

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    const load = () => api.health().then(setHealth).catch(() => setHealth(null));
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <InvestigationProvider>
      <div className="min-h-screen">
        <TopNav health={health} />
        <Routes>
          <Route path="/" element={<AdjusterPage />} />
          <Route path="/adjuster" element={<AdjusterPage />} />
          <Route path="/workflow" element={<Dashboard />} />
          <Route path="/claims" element={<ClaimsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </InvestigationProvider>
  );
}
