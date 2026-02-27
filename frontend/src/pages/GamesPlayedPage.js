import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getGamesPlayed } from "../lib/api";
import { formatFixed, toNumber } from "../lib/format";
import { useAsyncData } from "../lib/useAsyncData";
const GAMES_COLUMNS = [
    { key: "rank", label: "Rank", align: "right" },
    { key: "team_name", label: "Team", align: "left" },
    { key: "gp", label: "GP", align: "right" },
    { key: "rank_total", label: "PG Total", align: "right" },
    { key: "avg_gp_per_day_so_far", label: "GP/Day So Far", align: "right", render: (value) => formatFixed(value, 2) },
    {
        key: "avg_gp_per_day_needed",
        label: "GP/Day Remaining",
        align: "right",
        render: (value) => formatFixed(value, 2)
    },
    {
        key: "net_rate_delta",
        label: "Net Delta",
        align: "right",
        render: (value) => {
            const num = toNumber(value);
            if (num === null) {
                return "—";
            }
            const klass = num > 0 ? "delta delta-behind" : num < 0 ? "delta delta-ahead" : "delta";
            const display = `${num > 0 ? "+" : ""}${num.toFixed(2)}`;
            return _jsx("span", { className: klass, children: display });
        }
    }
];
export function GamesPlayedPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const startParam = searchParams.get("start") || undefined;
    const endParam = searchParams.get("end") || undefined;
    const totalGamesParam = searchParams.get("total_games") || undefined;
    const [form, setForm] = useState({ start: "", end: "", totalGames: "" });
    const loader = useCallback((signal) => getGamesPlayed({
        start: startParam,
        end: endParam,
        totalGames: totalGamesParam,
        signal
    }), [endParam, startParam, totalGamesParam]);
    const { data, loading, error, reload } = useAsyncData(loader, [startParam, endParam, totalGamesParam]);
    const hasData = Boolean(data?.has_data);
    const leagueId = data?.league_id ?? "";
    useEffect(() => {
        if (!data)
            return;
        setForm({
            start: startParam ?? data.start_str,
            end: endParam ?? data.end_str,
            totalGames: totalGamesParam ?? String(data.total_games)
        });
    }, [data, endParam, startParam, totalGamesParam]);
    function onSubmit(event) {
        event.preventDefault();
        const nextParams = new URLSearchParams(searchParams);
        if (form.start)
            nextParams.set("start", form.start);
        else
            nextParams.delete("start");
        if (form.end)
            nextParams.set("end", form.end);
        else
            nextParams.delete("end");
        if (form.totalGames)
            nextParams.set("total_games", form.totalGames);
        else
            nextParams.delete("total_games");
        setSearchParams(nextParams);
    }
    return (_jsxs(AppShell, { leagueId: leagueId, loading: loading, onReload: reload, scrapedAt: data?.scraped_at ?? null, children: [_jsx(StatusPanel, { emptyMessage: "No standings data yet. Go to Standings and run a refresh first.", error: error, hasData: hasData, loading: loading }), hasData && data ? (_jsxs(_Fragment, { children: [_jsxs("section", { children: [_jsx("h2", { children: "Season Window" }), _jsxs("form", { className: "gp-form", onSubmit: onSubmit, children: [_jsx("label", { htmlFor: "start", children: "Season start:" }), _jsx("input", { id: "start", onChange: (event) => setForm((prev) => ({ ...prev, start: event.target.value })), type: "date", value: form.start }), _jsx("label", { htmlFor: "end", children: "end:" }), _jsx("input", { id: "end", onChange: (event) => setForm((prev) => ({ ...prev, end: event.target.value })), type: "date", value: form.end }), _jsx("label", { htmlFor: "total-games", children: "Total annual games:" }), _jsx("input", { className: "gp-total-input", id: "total-games", min: 1, onChange: (event) => setForm((prev) => ({ ...prev, totalGames: event.target.value })), type: "number", value: form.totalGames }), _jsx("button", { type: "submit", children: "Update" })] }), data.date_error ? _jsx("p", { className: "panel error", children: data.date_error }) : null, data.date_valid ? (_jsxs("p", { className: "section-note", children: [_jsx("strong", { children: data.elapsed_days }), " days elapsed \u00B7 ", _jsx("strong", { children: data.remaining_days }), " days remaining (", data.start_str, " - ", data.end_str, ", inclusive)"] })) : null] }), _jsxs("section", { children: [_jsx("h2", { children: "Games Played Pace" }), _jsx(DataTable, { columns: GAMES_COLUMNS, initialSort: { key: "rank", desc: false }, rows: data.rows }), _jsxs("p", { className: "section-note gp-key", children: [_jsx("strong", { children: "GP/Day So Far" }), " - games played / elapsed days", _jsx("br", {}), _jsx("strong", { children: "GP/Day Remaining" }), " - (total games - GP) / remaining days: how many games per day you still need to play", _jsx("br", {}), _jsx("strong", { children: "Net Delta" }), " - GP/Day Remaining - GP/Day So Far: positive = need to speed up, negative = can slow down"] })] })] })) : null] }));
}
