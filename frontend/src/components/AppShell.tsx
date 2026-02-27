import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
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
            {scrapedAt ? <div className="meta">Updated {scrapedAt}</div> : null}
            <LeagueControls leagueId={leagueId} loading={loading} onReload={onReload} />
          </div>
        </div>
      </header>

      <main className="app-main">{children}</main>
    </div>
  );
}
