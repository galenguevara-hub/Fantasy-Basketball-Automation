import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { LeagueControls } from "./LeagueControls";
export function AppShell({ scrapedAt, leagueId, loading, onReload, children }) {
    const location = useLocation();
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef(null);
    useEffect(() => {
        setMenuOpen(false);
    }, [location.pathname]);
    useEffect(() => {
        function onDocumentClick(event) {
            const target = event.target;
            if (!menuRef.current?.contains(target)) {
                setMenuOpen(false);
            }
        }
        document.addEventListener("mousedown", onDocumentClick);
        return () => document.removeEventListener("mousedown", onDocumentClick);
    }, []);
    return (_jsxs("div", { className: "app-shell", children: [_jsx("header", { className: "app-header", children: _jsxs("div", { className: "header-row", children: [_jsxs("div", { className: "header-left", children: [_jsxs("div", { className: "nav-hamburger", ref: menuRef, children: [_jsxs("button", { "aria-expanded": menuOpen, "aria-label": "Open navigation menu", className: `hamburger-btn ${menuOpen ? "open" : ""}`, onClick: () => setMenuOpen((value) => !value), type: "button", children: [_jsx("span", {}), _jsx("span", {}), _jsx("span", {})] }), _jsxs("nav", { className: `hamburger-menu ${menuOpen ? "open" : ""}`, children: [_jsx(Link, { className: location.pathname === "/" ? "active" : "", to: "/", children: "Standings Analysis" }), _jsx(Link, { className: location.pathname === "/analysis" ? "active" : "", to: "/analysis", children: "Target Category Analysis" }), _jsx(Link, { className: location.pathname === "/games-played" ? "active" : "", to: "/games-played", children: "Games Played Analysis" })] })] }), _jsx("h1", { children: "Roto Fantasy Basketball Solver" })] }), _jsxs("div", { className: "header-right", children: [scrapedAt ? _jsxs("div", { className: "meta", children: ["Updated ", scrapedAt] }) : null, _jsx(LeagueControls, { leagueId: leagueId, loading: loading, onReload: onReload })] })] }) }), _jsx("main", { className: "app-main", children: children })] }));
}
