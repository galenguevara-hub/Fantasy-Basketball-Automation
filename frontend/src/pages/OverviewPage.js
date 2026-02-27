import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback } from "react";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getOverview } from "../lib/api";
import { formatCompact, formatFixed, toNumber } from "../lib/format";
import { useAsyncData } from "../lib/useAsyncData";
const OVERALL_COLUMNS = [
    { key: "rank", label: "Rank", align: "right" },
    { key: "team_name", label: "Team", align: "left" },
    { key: "GP", label: "GP", align: "right" },
    { key: "FG%", label: "FG%", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "FT%", label: "FT%", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "3PM", label: "3PM", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "PTS", label: "PTS", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "REB", label: "REB", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "AST", label: "AST", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "STL", label: "STL", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "BLK", label: "BLK", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "total_points", label: "Total", align: "right", render: (value) => formatCompact(value, 1) }
];
const PER_GAME_COLUMNS = [
    { key: "rank", label: "Rank", align: "right" },
    { key: "team_name", label: "Team", align: "left" },
    { key: "GP", label: "GP", align: "right" },
    { key: "FG%", label: "FG%", align: "right", render: (value) => formatFixed(value, 3) },
    { key: "FT%", label: "FT%", align: "right", render: (value) => formatFixed(value, 3) },
    { key: "3PM_pg", label: "3PM/G", align: "right", render: (value) => formatFixed(value, 3) },
    { key: "PTS_pg", label: "PTS/G", align: "right", render: (value) => formatFixed(value, 3) },
    { key: "REB_pg", label: "REB/G", align: "right", render: (value) => formatFixed(value, 3) },
    { key: "AST_pg", label: "AST/G", align: "right", render: (value) => formatFixed(value, 3) },
    { key: "ST_pg", label: "STL/G", align: "right", render: (value) => formatFixed(value, 3) },
    { key: "BLK_pg", label: "BLK/G", align: "right", render: (value) => formatFixed(value, 3) }
];
const OVERALL_STATS_COLUMNS = [
    { key: "rank", label: "Rank", align: "right" },
    { key: "team_name", label: "Team", align: "left" },
    { key: "GP", label: "GP", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "FG%", label: "FG%", align: "right", render: (value) => formatCompact(value, 3) },
    { key: "FT%", label: "FT%", align: "right", render: (value) => formatCompact(value, 3) },
    { key: "3PM", label: "3PM", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "PTS", label: "PTS", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "REB", label: "REB", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "AST", label: "AST", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "STL", label: "STL", align: "right", render: (value) => formatCompact(value, 1) },
    { key: "BLK", label: "BLK", align: "right", render: (value) => formatCompact(value, 1) }
];
const RANKING_COLUMNS = [
    { key: "rank", label: "Rank", align: "right" },
    { key: "team_name", label: "Team", align: "left" },
    { key: "GP", label: "GP", align: "right" },
    { key: "FG%_Rank", label: "FG%", align: "right" },
    { key: "FT%_Rank", label: "FT%", align: "right" },
    { key: "3PM_Rank", label: "3PM", align: "right" },
    { key: "PTS_Rank", label: "PTS", align: "right" },
    { key: "REB_Rank", label: "REB", align: "right" },
    { key: "AST_Rank", label: "AST", align: "right" },
    { key: "ST_Rank", label: "STL", align: "right" },
    { key: "BLK_Rank", label: "BLK", align: "right" },
    { key: "rank_total", label: "Total", align: "right", headerClassName: "col-total", cellClassName: "col-total" },
    {
        key: "points_delta",
        label: "Delta Total",
        align: "right",
        headerClassName: "col-total",
        cellClassName: "col-total",
        render: (value) => {
            const num = toNumber(value);
            if (num === null) {
                return "—";
            }
            const sign = num > 0 ? "+" : "";
            return `${sign}${num.toLocaleString("en-US", { maximumFractionDigits: 1 })}`;
        }
    }
];
function toOverallRows(teams) {
    return teams.map((team) => ({
        rank: team.rank,
        team_name: team.team_name,
        GP: team.stats.GP,
        "FG%": team.roto_points["FG%"],
        "FT%": team.roto_points["FT%"],
        "3PM": team.roto_points["3PTM"],
        PTS: team.roto_points.PTS,
        REB: team.roto_points.REB,
        AST: team.roto_points.AST,
        STL: team.roto_points.ST,
        BLK: team.roto_points.BLK,
        total_points: team.total_points
    }));
}
function toOverallStatsRows(teams) {
    return teams.map((team) => ({
        rank: team.rank,
        team_name: team.team_name,
        GP: team.stats.GP,
        "FG%": team.stats["FG%"],
        "FT%": team.stats["FT%"],
        "3PM": team.stats["3PTM"],
        PTS: team.stats.PTS,
        REB: team.stats.REB,
        AST: team.stats.AST,
        STL: team.stats.ST,
        BLK: team.stats.BLK
    }));
}
export function OverviewPage() {
    const loader = useCallback((signal) => getOverview(signal), []);
    const { data, loading, error, reload } = useAsyncData(loader, []);
    const hasData = Boolean(data?.has_data);
    const leagueId = data?.league_id ?? "";
    return (_jsxs(AppShell, { leagueId: leagueId, loading: loading, onReload: reload, scrapedAt: data?.scraped_at ?? null, children: [_jsx(StatusPanel, { emptyMessage: leagueId
                    ? "No standings data yet. Click Refresh to fetch standings."
                    : "No standings data yet. Enter your Yahoo league ID to get started.", error: error, hasData: hasData, loading: loading }), hasData && data ? (_jsxs(_Fragment, { children: [_jsxs("section", { children: [_jsx("h2", { children: "Overall Standings" }), _jsx("p", { className: "section-note", children: "Official Yahoo standings totals and category points." }), _jsx(DataTable, { columns: OVERALL_COLUMNS, initialSort: { key: "rank", desc: false }, rows: toOverallRows(data.teams) })] }), _jsxs("section", { children: [_jsx("h2", { children: "Overall Stats" }), _jsx("p", { className: "section-note", children: "Raw season totals from Yahoo before per-game normalization." }), _jsx(DataTable, { columns: OVERALL_STATS_COLUMNS, initialSort: { key: "rank", desc: false }, rows: toOverallStatsRows(data.teams) })] }), _jsxs("section", { children: [_jsx("h2", { children: "Per-Game Averages" }), _jsx("p", { className: "section-note", children: "Counting stats normalized by games played." }), _jsx(DataTable, { columns: PER_GAME_COLUMNS, initialSort: { key: "rank", desc: false }, rows: data.per_game_rows })] }), _jsxs("section", { children: [_jsx("h2", { children: "Per-Game Category Rankings" }), _jsx("p", { className: "section-note", children: "Each category ranked 1-10 based on per-game values (10 = best in league). Total is the sum of all category ranks. Delta Total is Total minus your actual roto points." }), _jsx(DataTable, { columns: RANKING_COLUMNS, initialSort: { key: "rank_total", desc: true }, rows: data.ranking_rows })] })] })) : null] }));
}
