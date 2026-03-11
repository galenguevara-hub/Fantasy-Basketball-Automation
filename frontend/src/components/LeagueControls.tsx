import { useEffect, useState } from "react";
import { ApiError, refreshStandings, saveConfig } from "../lib/api";

interface LeagueControlsProps {
  leagueId: string;
  loading: boolean;
  onReload: () => void;
  onAuthChange: () => void;
}

/**
 * Two-state flow:
 *   "input"     → User enters league ID and clicks Connect
 *   "connected" → League ID is set — show Refresh + Change
 *
 * Auth is on-demand: if any API call returns 401, redirect to Yahoo OAuth.
 */
type FlowState = "input" | "connected";

export function LeagueControls({ leagueId, loading, onReload, onAuthChange }: LeagueControlsProps) {
  const [flow, setFlow] = useState<FlowState>(leagueId ? "connected" : "input");
  const [editing, setEditing] = useState(false);
  const [input, setInput] = useState(leagueId);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const [cooldown, setCooldown] = useState<number | null>(null);

  useEffect(() => {
    setInput(leagueId);
    setFlow(leagueId ? "connected" : "input");
  }, [leagueId]);

  // Tick the cooldown down by 1 every second until it reaches 0.
  useEffect(() => {
    if (cooldown === null || cooldown <= 0) {
      if (cooldown !== null && cooldown <= 0) setCooldown(null);
      return;
    }
    const timer = window.setTimeout(() => {
      setCooldown((prev) => (prev !== null && prev > 1 ? prev - 1 : null));
    }, 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  function show(msg: string, error = false) {
    setMessage(msg);
    setIsError(error);
    window.setTimeout(() => {
      setMessage((current) => (current === msg ? null : current));
    }, error ? 5000 : 2500);
  }

  function handleRateLimitError(err: unknown) {
    if (err instanceof ApiError && err.status === 429) {
      setCooldown(err.retryAfter ?? 30);
      return true;
    }
    return false;
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
      setFlow("connected");
      setEditing(false);
      onAuthChange();
      show("League connected and standings refreshed.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        window.open("/auth/yahoo", "_blank");
        return;
      }
      if (handleRateLimitError(err)) return;
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
      if (err instanceof ApiError && err.status === 401) {
        window.open("/auth/yahoo", "_blank");
        return;
      }
      if (handleRateLimitError(err)) return;
      const detail = err instanceof Error ? err.message : "Unable to refresh";
      show(detail, true);
    } finally {
      setBusy(false);
    }
  }

  const disabled = busy || loading || cooldown !== null;
  const toastMessage = cooldown !== null ? `Please wait ${cooldown}s to refresh again.` : message;
  const toastError = cooldown !== null ? true : isError;

  // --- input: enter league ID ---
  if (flow === "input" || editing) {
    return (
      <div className="league-controls-wrap">
        <div className="league-controls">
          <input
            aria-label="League ID"
            maxLength={10}
            placeholder="League ID"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void onConnect(); }}
          />
          <button disabled={disabled} onClick={() => void onConnect()} type="button">
            {busy ? "Connecting..." : "Connect"}
          </button>
          {leagueId ? (
            <button className="ghost" disabled={disabled} onClick={() => { setEditing(false); setFlow("connected"); }} type="button">
              Cancel
            </button>
          ) : null}
        </div>
        {toastMessage ? <div className={toastError ? "toast error" : "toast"}>{toastMessage}</div> : null}
      </div>
    );
  }

  // --- connected: show league info + refresh ---
  return (
    <div className="league-controls-wrap">
      <div className="league-controls">
        <span className="meta">League {leagueId}</span>
        <button className="ghost" disabled={disabled} onClick={() => setEditing(true)} type="button">
          Change
        </button>
        <button disabled={disabled} onClick={() => void onRefresh()} type="button">
          {busy ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      {toastMessage ? <div className={toastError ? "toast error" : "toast"}>{toastMessage}</div> : null}
    </div>
  );
}
