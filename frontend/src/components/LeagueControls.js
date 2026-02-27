import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { refreshStandings, saveConfig } from "../lib/api";
export function LeagueControls({ leagueId, loading, onReload }) {
    const [editing, setEditing] = useState(!leagueId);
    const [input, setInput] = useState(leagueId);
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState(null);
    const [isError, setIsError] = useState(false);
    useEffect(() => {
        setInput(leagueId);
        setEditing(!leagueId);
    }, [leagueId]);
    function show(msg, error = false) {
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
        }
        catch (err) {
            const detail = err instanceof Error ? err.message : "Unable to connect league";
            show(detail, true);
        }
        finally {
            setBusy(false);
        }
    }
    async function onRefresh() {
        setBusy(true);
        try {
            await runRefresh();
            show("Standings refreshed.");
        }
        catch (err) {
            const detail = err instanceof Error ? err.message : "Unable to refresh";
            show(detail, true);
        }
        finally {
            setBusy(false);
        }
    }
    const disabled = busy || loading;
    return (_jsxs("div", { className: "league-controls-wrap", children: [editing ? (_jsxs("div", { className: "league-controls", children: [_jsx("input", { "aria-label": "League ID", maxLength: 10, placeholder: "League ID", type: "text", value: input, onChange: (event) => setInput(event.target.value) }), _jsx("button", { disabled: disabled, onClick: () => void onConnect(), type: "button", children: busy ? "Connecting..." : "Connect" }), leagueId ? (_jsx("button", { className: "ghost", disabled: disabled, onClick: () => setEditing(false), type: "button", children: "Cancel" })) : null] })) : (_jsxs("div", { className: "league-controls", children: [_jsxs("span", { className: "meta", children: ["League ", leagueId] }), _jsx("button", { className: "ghost", disabled: disabled, onClick: () => setEditing(true), type: "button", children: "Change" }), _jsx("button", { disabled: disabled, onClick: () => void onRefresh(), type: "button", children: busy ? "Refreshing..." : "Refresh" })] })), message ? _jsx("div", { className: isError ? "toast error" : "toast", children: message }) : null] }));
}
