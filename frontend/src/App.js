import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Navigate, Route, Routes } from "react-router-dom";
import { AnalysisPage } from "./pages/AnalysisPage";
import { GamesPlayedPage } from "./pages/GamesPlayedPage";
import { OverviewPage } from "./pages/OverviewPage";
export function App() {
    return (_jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(OverviewPage, {}) }), _jsx(Route, { path: "/analysis", element: _jsx(AnalysisPage, {}) }), _jsx(Route, { path: "/games-played", element: _jsx(GamesPlayedPage, {}) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/", replace: true }) })] }));
}
