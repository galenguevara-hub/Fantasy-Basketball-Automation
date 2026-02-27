import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getAnalysis } from "../lib/api";
import { formatFixed, toNumber } from "../lib/format";
import { useAsyncData } from "../lib/useAsyncData";
const CAT_CLASS_MAP = {
    "FG%": "cat-fg",
    "FT%": "cat-ft",
    "3PM/G": "cat-3pm",
    "PTS/G": "cat-pts",
    "REB/G": "cat-reb",
    "AST/G": "cat-ast",
    "STL/G": "cat-stl",
    "BLK/G": "cat-blk"
};
function renderTagPill(tag) {
    if (tag !== "TARGET" && tag !== "DEFEND") {
        return "—";
    }
    return _jsx("span", { className: `tag ${tag === "TARGET" ? "tag-target" : "tag-defend"}`, children: tag });
}
function normalizeCategory(value) {
    if (typeof value === "string") {
        return value;
    }
    if (value && typeof value === "object" && "display" in value) {
        const display = value.display;
        if (typeof display === "string") {
            return display;
        }
    }
    return null;
}
function renderCategoryList(value) {
    if (!Array.isArray(value) || value.length === 0) {
        return "—";
    }
    const categories = value
        .map(normalizeCategory)
        .filter((item) => Boolean(item));
    if (categories.length === 0) {
        return "—";
    }
    return (_jsx("div", { className: "tag-list", children: categories.map((category) => (_jsx("span", { className: `tag ${CAT_CLASS_MAP[category] ?? ""}`, children: category.replace("/G", "") }, category))) }));
}
function renderTeamWithRank(value, teamPgRank) {
    if (typeof value !== "string" || value.length === 0) {
        return "—";
    }
    const rank = teamPgRank[value];
    return (_jsxs(_Fragment, { children: [value, rank ? _jsxs("span", { className: "ref-rank", children: [" (", rank, ")"] }) : null] }));
}
function analysisColumns(teamPgRank) {
    return [
        {
            key: "display",
            label: "Category",
            align: "left",
            headerClassName: "col-cat",
            cellClassName: "col-cat"
        },
        { key: "value", label: "Value", align: "right", render: (value) => formatFixed(value, 3) },
        { key: "rank", label: "Rank", align: "right" },
        {
            key: "next_better_team",
            label: "Better Team",
            align: "left",
            headerClassName: "col-ref",
            cellClassName: "col-ref",
            render: (value) => renderTeamWithRank(value, teamPgRank)
        },
        { key: "next_better_value", label: "Value", align: "right", render: (value) => formatFixed(value, 3) },
        { key: "gap_up", label: "Gap+", align: "right", render: (value) => formatFixed(value, 3) },
        { key: "z_gap_up", label: "z+", align: "right", render: (value) => formatFixed(value, 2) },
        {
            key: "next_worse_team",
            label: "Worse Team",
            align: "left",
            headerClassName: "col-ref",
            cellClassName: "col-ref",
            render: (value) => renderTeamWithRank(value, teamPgRank)
        },
        { key: "next_worse_value", label: "Value", align: "right", render: (value) => formatFixed(value, 3) },
        { key: "gap_down", label: "Gap−", align: "right", render: (value) => formatFixed(value, 3) },
        { key: "z_gap_down", label: "z−", align: "right", render: (value) => formatFixed(value, 2) },
        { key: "target_score", label: "Score", align: "right", render: (value) => formatFixed(value, 2) },
        { key: "tag", label: "Tag", align: "center", cellClassName: "col-tag", render: renderTagPill }
    ];
}
const LEAGUE_COLUMNS = [
    { key: "pg_rank", label: "PG Rank", align: "right" },
    { key: "team_name", label: "Team", align: "left" },
    {
        key: "rank_total",
        label: "PG Total",
        align: "right",
        render: (value) => {
            const num = toNumber(value);
            return num === null ? "—" : String(num);
        }
    },
    {
        key: "total_points",
        label: "Roto Total",
        align: "right",
        render: (value) => {
            const num = toNumber(value);
            return num === null ? "—" : num.toLocaleString("en-US", { maximumFractionDigits: 1 });
        }
    },
    { key: "targets", label: "L1 Targets", align: "left", render: renderCategoryList },
    { key: "defends", label: "L1 Defends", align: "left", render: renderCategoryList },
    { key: "cluster_targets", label: "Cluster Targets", align: "left", render: renderCategoryList },
    { key: "cluster_defends", label: "Cluster Defends", align: "left", render: renderCategoryList }
];
function formatSigma(value, category) {
    const num = toNumber(value);
    if (num === null)
        return "—";
    return category === "FG%" || category === "FT%" ? num.toFixed(4) : num.toFixed(3);
}
function formatPlain(value) {
    const num = toNumber(value);
    return num === null ? "—" : String(num);
}
const CLUSTER_COLUMNS = [
    { key: "display", label: "Category", align: "left" },
    { key: "rank", label: "Rank", align: "right" },
    { key: "sigma", label: "σ", align: "right", render: (value, row) => formatSigma(value, row.category) },
    { key: "z_to_gain_1", label: "z+1", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "z_to_gain_2", label: "z+2", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "z_to_gain_3", label: "z+3", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "points_up_within_T", label: "Pts Up ≤ 0.75σ", align: "right", render: formatPlain },
    { key: "cluster_up_score", label: "Up Score", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "z_to_lose_1", label: "z−1", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "z_to_lose_2", label: "z−2", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "z_to_lose_3", label: "z−3", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "points_down_within_T", label: "Pts Down ≤ 0.75σ", align: "right", render: formatPlain },
    { key: "cluster_down_risk", label: "Dn Risk", align: "right", render: (value) => formatFixed(value, 2) },
    { key: "tag", label: "Tag", align: "center", render: renderTagPill }
];
export function AnalysisPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const requestedTeam = searchParams.get("team")?.trim() || undefined;
    const loader = useCallback((signal) => getAnalysis(requestedTeam, signal), [requestedTeam]);
    const { data, loading, error, reload } = useAsyncData(loader, [requestedTeam]);
    const hasData = Boolean(data?.has_data);
    const leagueId = data?.league_id ?? "";
    function onTeamChange(event) {
        const next = event.target.value;
        const nextParams = new URLSearchParams(searchParams);
        if (next) {
            nextParams.set("team", next);
        }
        else {
            nextParams.delete("team");
        }
        setSearchParams(nextParams);
    }
    const analysisRows = data?.analysis ?? [];
    const targetRows = analysisRows.filter((row) => row.tag === "TARGET");
    const defendRows = analysisRows.filter((row) => row.tag === "DEFEND");
    const teamPgRank = data?.team_pg_rank ?? {};
    const leagueRows = data?.league_summary ?? [];
    const clusterRows = analysisRows.map((row) => {
        const item = row;
        const categoryKey = typeof item.category === "string" ? item.category : "";
        const teamCluster = (data?.team_cluster ?? {});
        const clusterMetrics = teamCluster[categoryKey] ?? {};
        return {
            display: item.display,
            category: item.category,
            rank: item.rank,
            sigma: clusterMetrics.sigma,
            z_to_gain_1: clusterMetrics.z_to_gain_1,
            z_to_gain_2: clusterMetrics.z_to_gain_2,
            z_to_gain_3: clusterMetrics.z_to_gain_3,
            points_up_within_T: clusterMetrics.points_up_within_T,
            cluster_up_score: clusterMetrics.cluster_up_score,
            z_to_lose_1: clusterMetrics.z_to_lose_1,
            z_to_lose_2: clusterMetrics.z_to_lose_2,
            z_to_lose_3: clusterMetrics.z_to_lose_3,
            points_down_within_T: clusterMetrics.points_down_within_T,
            cluster_down_risk: clusterMetrics.cluster_down_risk,
            tag: clusterMetrics.tag
        };
    });
    return (_jsxs(AppShell, { leagueId: leagueId, loading: loading, onReload: reload, scrapedAt: data?.scraped_at ?? null, children: [_jsx(StatusPanel, { emptyMessage: "No standings data yet. Go to Standings and run a refresh first.", error: error, hasData: hasData, loading: loading }), hasData && data ? (_jsxs(_Fragment, { children: [analysisRows.length > 0 ? (_jsxs("section", { className: "summary-panel", children: [_jsxs("div", { className: "summary-group summary-target", children: [_jsx("h3", { children: "Categories to Target" }), _jsx("p", { className: "summary-note", children: "Best ROI - smallest effort for +1 roto point" }), _jsx("ul", { children: targetRows.map((row) => (_jsxs("li", { children: [_jsx("strong", { children: row.display }), _jsx("span", { className: "summary-detail", children: row.z_gap_up === null ? "—" : `${formatFixed(row.z_gap_up, 2)}σ to gain a rank` })] }, `target-${row.category}`))) })] }), _jsxs("div", { className: "summary-group summary-defend", children: [_jsx("h3", { children: "Categories to Defend" }), _jsx("p", { className: "summary-note", children: "Smallest buffer - risk of losing -1 roto point" }), _jsx("ul", { children: defendRows.map((row) => (_jsxs("li", { children: [_jsx("strong", { children: row.display }), _jsx("span", { className: "summary-detail", children: row.z_gap_down === null ? "—" : `${formatFixed(row.z_gap_down, 2)}σ buffer` })] }, `defend-${row.category}`))) })] })] })) : null, _jsxs("section", { children: [_jsxs("h2", { children: ["Category Analysis - ", data.selected_team] }), _jsxs("div", { className: "control-row", children: [_jsx("label", { htmlFor: "team-select", children: "Analyze team" }), _jsx("select", { id: "team-select", onChange: onTeamChange, value: data.selected_team ?? "", children: data.team_names.map((name) => (_jsx("option", { value: name, children: name }, name))) })] }), _jsx(DataTable, { columns: analysisColumns(teamPgRank), initialSort: { key: "target_score", desc: true }, rowClassName: (row) => {
                                    const tag = row.tag;
                                    if (tag === "TARGET")
                                        return "row-target";
                                    if (tag === "DEFEND")
                                        return "row-defend";
                                    return undefined;
                                }, rows: analysisRows, tableClassName: "analysis-table" })] }), _jsxs("aside", { className: "analysis-key", "aria-label": "How to read this table", children: [_jsx("h4", { className: "analysis-key-title", children: "How to read this" }), _jsxs("ul", { className: "analysis-key-list", children: [_jsxs("li", { children: [_jsx("strong", { children: "z+ (Effort):" }), " Standard deviations you must improve to pass the next team \u2014 lower is easier to close."] }), _jsxs("li", { children: [_jsx("strong", { children: "z\u2212 (Risk):" }), " Standard deviations separating you from the team behind \u2014 lower means you're more vulnerable."] }), _jsxs("li", { children: [_jsx("strong", { children: "Score:" }), " Higher = better ROI. Prioritizes easy gains, lightly weights downside protection."] })] }), _jsxs("div", { className: "analysis-key-rules", children: [_jsxs("span", { children: [_jsx("strong", { children: "Rule of thumb \u2014" }), " z+ < 0.40: great target \u00B7 0.40-0.75: possible \u00B7 > 0.75: usually not worth chasing"] }), _jsxs("span", { children: [_jsx("strong", { children: "Risk \u2014" }), " z\u2212 < 0.30: defend this category"] })] }), _jsx("p", { className: "analysis-key-example", children: "Example: STL with z+ = 0.18 is a high-leverage target \u2014 a small improvement can gain a roto point." })] }), analysisRows.length > 0 && Object.keys(data.team_cluster ?? {}).length > 0 ? (_jsxs("section", { children: [_jsx("h2", { children: "Cluster Leverage (Multi-Point Potential)" }), _jsx("p", { className: "section-note", children: "This measures how many roto points you can gain (or lose) if teams are tightly clustered. It looks beyond the next opponent." }), _jsx(DataTable, { columns: CLUSTER_COLUMNS, initialSort: { key: "cluster_up_score", desc: true }, rowClassName: (row) => {
                                    const tag = row.tag;
                                    if (tag === "TARGET")
                                        return "row-target";
                                    if (tag === "DEFEND")
                                        return "row-defend";
                                    return undefined;
                                }, rows: clusterRows, tableClassName: "analysis-table cluster-table" }), _jsxs("aside", { className: "cluster-legend", children: [_jsx("h4", { className: "analysis-key-title", children: "How to read this" }), _jsxs("ul", { className: "analysis-key-list", children: [_jsxs("li", { children: [_jsx("strong", { children: "\u03C3 (Sigma):" }), " Population std dev for this category \u2014 the natural unit of spread across all teams."] }), _jsxs("li", { children: [_jsx("strong", { children: "z+1 / z+2 / z+3:" }), " Standardized improvement (in \u03C3 units) needed to jump 1, 2, or 3 roto points upward. Smaller = more reachable. \"\u2014\" means you're already at or beyond that tier."] }), _jsxs("li", { children: [_jsx("strong", { children: "z\u22121 / z\u22122 / z\u22123:" }), " Standardized decline (in \u03C3 units) needed to drop 1, 2, or 3 roto points downward. Smaller = more fragile. \"\u2014\" means you're already at the bottom tier."] }), _jsxs("li", { children: [_jsx("strong", { children: "Pts Up:" }), " How many roto-point jumps sit within a 0.75\u03C3 effort window above you \u2014 teams bunched close enough that one push gains multiple spots."] }), _jsxs("li", { children: [_jsx("strong", { children: "Up Score:" }), " Pts Up \u00F7 0.75 \u2014 a density-adjusted ROI. Higher = more multi-point leverage per unit of effort."] }), _jsxs("li", { children: [_jsx("strong", { children: "Pts Dn:" }), " How many roto-point drops sit within 0.75\u03C3 below you \u2014 teams so close that a small slip costs multiple positions."] }), _jsxs("li", { children: [_jsx("strong", { children: "Dn Risk:" }), " Pts Dn \u00F7 0.75 \u2014 a density-adjusted fragility score. Higher = more exposure to a multi-point collapse."] })] }), _jsxs("div", { className: "analysis-key-rules", children: [_jsxs("span", { children: [_jsx("strong", { children: "High Cluster Up Score" }), " = can gain multiple points with modest improvement \u2014 prioritize this category."] }), _jsxs("span", { children: [_jsx("strong", { children: "High Cluster Down Risk" }), " = could lose multiple points if you slip \u2014 defend this category."] })] })] })] })) : null, _jsxs("section", { children: [_jsx("h2", { children: "League Overview" }), _jsx("p", { className: "section-note", children: "All teams ranked by per-game total (highest = best). Layer 1 and Cluster target/defend categories are sorted from highest to lowest priority score." }), _jsx(DataTable, { columns: LEAGUE_COLUMNS, initialSort: { key: "rank_total", desc: true }, rows: leagueRows })] })] })) : null] }));
}
