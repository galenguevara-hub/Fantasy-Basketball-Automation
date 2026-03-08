import { Navigate, Route, Routes } from "react-router-dom";
import { AnalysisPage } from "./pages/AnalysisPage";
import { ExecutiveSummaryPage } from "./pages/ExecutiveSummaryPage";
import { GamesPlayedPage } from "./pages/GamesPlayedPage";
import { OverviewPage } from "./pages/OverviewPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<ExecutiveSummaryPage />} />
      <Route path="/executive-summary" element={<ExecutiveSummaryPage />} />
      <Route path="/standings" element={<OverviewPage />} />
      <Route path="/analysis" element={<AnalysisPage />} />
      <Route path="/games-played" element={<GamesPlayedPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
