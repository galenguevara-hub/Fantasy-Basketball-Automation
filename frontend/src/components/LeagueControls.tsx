import { useEffect, useState } from "react";
import { refreshStandings, saveConfig } from "../lib/api";

interface LeagueControlsProps {
  leagueId: string;
  loading: boolean;
  onReload: () => void;
}

export function LeagueControls({ leagueId, loading, onReload }: LeagueControlsProps) {
  const [editing, setEditing] = useState(!leagueId);
  const [input, setInput] = useState(leagueId);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    setInput(leagueId);
    setEditing(!leagueId);
  }, [leagueId]);

  function show(msg: string, error = false) {
    setMessage(msg);
    setIsError(error);
    window.setTimeout(() => {
      setMessage((current) => (current === msg ? null : current));
    }, error ? 5000 : 2500);
  }

  async function runRefresh() {
    await refreshStandings();
    onReload();
  }

  async function onConnect() {
    const value = input.trim();
    if (!value) {
      show("League ID is required.", true);
      return;
    }
    if (!/^\d+$/.test(value)) {
      show("League ID must be numeric.", true);
      return;
    }

    setBusy(true);
    try {
      await saveConfig(value);
      await runRefresh();
      setEditing(false);
      show("League connected and standings refreshed.");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Unable to connect league";
      show(detail, true);
    } finally {
      setBusy(false);
    }
  }

  async function onRefresh() {
    setBusy(true);
    try {
      await runRefresh();
      show("Standings refreshed.");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Unable to refresh";
      show(detail, true);
    } finally {
      setBusy(false);
    }
  }

  const disabled = busy || loading;

  return (
    <div className="league-controls-wrap">
      {editing ? (
        <div className="league-controls">
          <input
            aria-label="League ID"
            maxLength={10}
            placeholder="League ID"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <button disabled={disabled} onClick={() => void onConnect()} type="button">
            {busy ? "Connecting..." : "Connect"}
          </button>
          {leagueId ? (
            <button className="ghost" disabled={disabled} onClick={() => setEditing(false)} type="button">
              Cancel
            </button>
          ) : null}
        </div>
      ) : (
        <div className="league-controls">
          <span className="meta">League {leagueId}</span>
          <button className="ghost" disabled={disabled} onClick={() => setEditing(true)} type="button">
            Change
          </button>
          <button disabled={disabled} onClick={() => void onRefresh()} type="button">
            {busy ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      )}

      {message ? <div className={isError ? "toast error" : "toast"}>{message}</div> : null}
    </div>
  );
}
