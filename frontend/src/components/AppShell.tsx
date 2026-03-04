import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { getAuthStatus, logout } from "../lib/api";
import { LeagueControls } from "./LeagueControls";

interface AppShellProps {
  scrapedAt: string | null;
  leagueId: string;
  loading: boolean;
  onReload: () => void;
  children: ReactNode;
}

export function AppShell({ scrapedAt, leagueId, loading, onReload, children }: AppShellProps) {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [userName, setUserName] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getAuthStatus(controller.signal)
      .then((auth) => {
        setAuthenticated(auth.authenticated);
        setUserName(auth.user_name ?? "");
      })
      .catch(() => {
        setAuthenticated(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    function onDocumentClick(event: MouseEvent) {
      const target = event.target as Node;
      if (!menuRef.current?.contains(target)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, []);

  function refreshAuth() {
    getAuthStatus()
      .then((auth) => {
        setAuthenticated(auth.authenticated);
        setUserName(auth.user_name ?? "");
      })
      .catch(() => setAuthenticated(false));
  }

  async function handleLogout() {
    await logout();
    window.location.reload();
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-row">
          <div className="header-left">
            <div className="nav-hamburger" ref={menuRef}>
              <button
                aria-expanded={menuOpen}
                aria-label="Open navigation menu"
                className={`hamburger-btn ${menuOpen ? "open" : ""}`}
                onClick={() => setMenuOpen((value) => !value)}
                type="button"
              >
                <span />
                <span />
                <span />
              </button>
              <nav className={`hamburger-menu ${menuOpen ? "open" : ""}`}>
                <Link className={location.pathname === "/" ? "active" : ""} to="/">
                  Standings Analysis
                </Link>
                <Link className={location.pathname === "/analysis" ? "active" : ""} to="/analysis">
                  Target Category Analysis
                </Link>
                <Link className={location.pathname === "/games-played" ? "active" : ""} to="/games-played">
                  Games Played Analysis
                </Link>
              </nav>
            </div>
            <h1>Roto Fantasy Basketball Solver</h1>
          </div>

          <div className="header-right">
            {scrapedAt ? <div className="meta">Updated {new Date(scrapedAt).toLocaleString()}</div> : null}
            <div className="header-controls">
              <LeagueControls
                leagueId={leagueId}
                loading={loading}
                onReload={onReload}
                onAuthChange={refreshAuth}
              />
              {authenticated ? (
                <button className="ghost" onClick={() => void handleLogout()} type="button">
                  Logout
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      <main className="app-main">{children}</main>
    </div>
  );
}
