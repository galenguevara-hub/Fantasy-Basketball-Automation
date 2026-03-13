import { useCallback, useEffect, useMemo, useRef } from "react";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getOverview, refreshStandings } from "../lib/api";
import { formatCompact, formatFixed, toNumber } from "../lib/format";
import type { CategoryMeta, TeamRow } from "../lib/types";
import { useAsyncData } from "../lib/useAsyncData";

// Fallback 8-cat config if backend doesn't provide category_config
const FALLBACK_CONFIG: CategoryMeta[] = [
  { key: "FG%", display: "FG%", stat_id: 5, higher_is_better: true, is_percentage: true, per_game_key: null, per_game_display: "FG%", rank_key: "FG%_Rank" },
  { key: "FT%", display: "FT%", stat_id: 8, higher_is_better: true, is_percentage: true, per_game_key: null, per_game_display: "FT%", rank_key: "FT%_Rank" },
  { key: "3PTM", display: "3PM", stat_id: 10, higher_is_better: true, is_percentage: false, per_game_key: "3PTM_pg", per_game_display: "3PM/G", rank_key: "3PTM_Rank" },
  { key: "PTS", display: "PTS", stat_id: 12, higher_is_better: true, is_percentage: false, per_game_key: "PTS_pg", per_game_display: "PTS/G", rank_key: "PTS_Rank" },
  { key: "REB", display: "REB", stat_id: 15, higher_is_better: true, is_percentage: false, per_game_key: "REB_pg", per_game_display: "REB/G", rank_key: "REB_Rank" },
  { key: "AST", display: "AST", stat_id: 16, higher_is_better: true, is_percentage: false, per_game_key: "AST_pg", per_game_display: "AST/G", rank_key: "AST_Rank" },
  { key: "ST", display: "STL", stat_id: 17, higher_is_better: true, is_percentage: false, per_game_key: "ST_pg", per_game_display: "STL/G", rank_key: "ST_Rank" },
  { key: "BLK", display: "BLK", stat_id: 18, higher_is_better: true, is_percentage: false, per_game_key: "BLK_pg", per_game_display: "BLK/G", rank_key: "BLK_Rank" },
];

function buildOverallColumns(config: CategoryMeta[]) {
  return [
    { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
    { key: "rank", label: "Rank", align: "right" as const },
    { key: "GP", label: "GP", align: "right" as const },
    ...config.map((c) => ({
      key: c.key,
      label: c.display,
      align: "right" as const,
      render: (value: unknown) => formatCompact(value, 1),
    })),
    { key: "total_points", label: "Total", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  ];
}

function buildPerGameColumns(config: CategoryMeta[]) {
  return [
    { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
    { key: "rank", label: "Rank", align: "right" as const },
    { key: "GP", label: "GP", align: "right" as const },
    ...config.map((c) => {
      const dataKey = c.per_game_key ?? c.key;
      return {
        key: dataKey,
        label: c.per_game_display,
        align: "right" as const,
        render: (value: unknown) => c.is_percentage ? formatFixed(value, 4) : formatFixed(value, 3),
      };
    }),
  ];
}

function buildOverallStatsColumns(config: CategoryMeta[]) {
  return [
    { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
    { key: "rank", label: "Rank", align: "right" as const },
    { key: "GP", label: "GP", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
    ...config.map((c) => ({
      key: c.key,
      label: c.display,
      align: "right" as const,
      render: (value: unknown) => c.is_percentage ? formatFixed(value, 4) : formatCompact(value, 1),
    })),
  ];
}

function buildRankingColumns(config: CategoryMeta[]) {
  return [
    { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
    { key: "rank", label: "Rank", align: "right" as const },
    { key: "GP", label: "GP", align: "right" as const },
    ...config.map((c) => ({
      key: c.rank_key,
      label: c.display,
      align: "right" as const,
    })),
    { key: "rank_total", label: "Total", align: "right" as const, headerClassName: "col-total", cellClassName: "col-total" },
    {
      key: "points_delta",
      label: "Delta Total",
      align: "right" as const,
      headerClassName: "col-total",
      cellClassName: "col-total",
      render: (value: unknown) => {
        const num = toNumber(value);
        if (num === null) {
          return "—";
        }
        const sign = num > 0 ? "+" : "";
        return `${sign}${num.toLocaleString("en-US", { maximumFractionDigits: 1 })}`;
      },
    },
  ];
}

function toOverallRows(teams: TeamRow[], config: CategoryMeta[]) {
  return teams.map((team) => {
    const row: Record<string, unknown> = {
      rank: team.rank,
      team_name: team.team_name,
      GP: team.stats.GP,
      total_points: team.total_points,
    };
    for (const c of config) {
      row[c.key] = team.roto_points[c.key];
    }
    return row;
  });
}

function toOverallStatsRows(teams: TeamRow[], config: CategoryMeta[]) {
  return teams.map((team) => {
    const row: Record<string, unknown> = {
      rank: team.rank,
      team_name: team.team_name,
      GP: team.stats.GP,
    };
    for (const c of config) {
      row[c.key] = team.stats[c.key];
    }
    return row;
  });
}

export function OverviewPage() {
  const loader = useCallback((signal: AbortSignal) => getOverview(signal), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);
  const autoRefreshed = useRef(false);

  const catConfig = data?.category_config ?? FALLBACK_CONFIG;

  const overallColumns = useMemo(() => buildOverallColumns(catConfig), [catConfig]);
  const perGameColumns = useMemo(() => buildPerGameColumns(catConfig), [catConfig]);
  const overallStatsColumns = useMemo(() => buildOverallStatsColumns(catConfig), [catConfig]);
  const rankingColumns = useMemo(() => buildRankingColumns(catConfig), [catConfig]);

  const perGameRows = data?.per_game_rows ?? [];

  const hasData = Boolean(data?.has_data);
  const leagueId = data?.league_id ?? "";

  // Step F: Auto-refresh on return if league ID is set but no cached data
  useEffect(() => {
    if (leagueId && !hasData && !loading && !error && !autoRefreshed.current) {
      autoRefreshed.current = true;
      refreshStandings()
        .then(() => reload())
        .catch(() => {
          // 401 = not authenticated, user will need to re-auth via Connect flow
          // Other errors are ignored — user can click Refresh manually
        });
    }
  }, [leagueId, hasData, loading, error, reload]);

  return (
    <AppShell leagueId={leagueId} loading={loading} onReload={reload} scrapedAt={data?.scraped_at ?? null}>
      <StatusPanel
        emptyMessage={
          leagueId
            ? "No standings data yet. Click Refresh to fetch standings."
            : "No standings data yet. Enter your Yahoo league ID to get started."
        }
        error={error}
        hasData={hasData}
        loading={loading}
      />

      {hasData && data ? (
        <>
          <section>
            <h2>Overall Standings</h2>
            <p className="section-note">Official Yahoo standings totals and category points.</p>
            <DataTable columns={overallColumns} initialSort={{ key: "rank", desc: false }} rows={toOverallRows(data.teams, catConfig)} />
          </section>

          <section>
            <h2>Overall Stats</h2>
            <p className="section-note">Raw season totals from Yahoo before per-game normalization.</p>
            <DataTable columns={overallStatsColumns} initialSort={{ key: "rank", desc: false }} rows={toOverallStatsRows(data.teams, catConfig)} />
          </section>

          <section>
            <h2>Per-Game Averages</h2>
            <p className="section-note">Counting stats normalized by games played.</p>
            <DataTable columns={perGameColumns} initialSort={{ key: "rank", desc: false }} rows={perGameRows} />
          </section>

          <section>
            <h2>Per-Game Category Rankings</h2>
            <p className="section-note">
              Each category ranked 1-10 based on per-game values (10 = best in league). Total is the sum of all category
              ranks. Delta Total is Total minus your actual roto points.
            </p>
            <DataTable columns={rankingColumns} initialSort={{ key: "rank_total", desc: true }} rows={data.ranking_rows} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
