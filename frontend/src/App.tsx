import { Navigate, Route, Routes } from "react-router-dom";
import { AnalysisPage } from "./pages/AnalysisPage";
import { GamesPlayedPage } from "./pages/GamesPlayedPage";
import { OverviewPage } from "./pages/OverviewPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/analysis" element={<AnalysisPage />} />
      <Route path="/games-played" element={<GamesPlayedPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
