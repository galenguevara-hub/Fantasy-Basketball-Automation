import { useCallback } from "react";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getOverview } from "../lib/api";
import { formatCompact, formatFixed, toNumber } from "../lib/format";
import type { TeamRow } from "../lib/types";
import { useAsyncData } from "../lib/useAsyncData";

const OVERALL_COLUMNS = [
  { key: "rank", label: "Rank", align: "right" as const },
  { key: "team_name", label: "Team", align: "left" as const },
  { key: "GP", label: "GP", align: "right" as const },
  { key: "FG%", label: "FG%", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "FT%", label: "FT%", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "3PM", label: "3PM", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "PTS", label: "PTS", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "REB", label: "REB", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "AST", label: "AST", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "STL", label: "STL", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "BLK", label: "BLK", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "total_points", label: "Total", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) }
];

const PER_GAME_COLUMNS = [
  { key: "rank", label: "Rank", align: "right" as const },
  { key: "team_name", label: "Team", align: "left" as const },
  { key: "GP", label: "GP", align: "right" as const },
  { key: "FG%", label: "FG%", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
  { key: "FT%", label: "FT%", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
  { key: "3PM_pg", label: "3PM/G", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
  { key: "PTS_pg", label: "PTS/G", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
  { key: "REB_pg", label: "REB/G", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
  { key: "AST_pg", label: "AST/G", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
  { key: "ST_pg", label: "STL/G", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
  { key: "BLK_pg", label: "BLK/G", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) }
];

const OVERALL_STATS_COLUMNS = [
  { key: "rank", label: "Rank", align: "right" as const },
  { key: "team_name", label: "Team", align: "left" as const },
  { key: "GP", label: "GP", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "FG%", label: "FG%", align: "right" as const, render: (value: unknown) => formatCompact(value, 3) },
  { key: "FT%", label: "FT%", align: "right" as const, render: (value: unknown) => formatCompact(value, 3) },
  { key: "3PM", label: "3PM", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "PTS", label: "PTS", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "REB", label: "REB", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "AST", label: "AST", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "STL", label: "STL", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "BLK", label: "BLK", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) }
];

const RANKING_COLUMNS = [
  { key: "rank", label: "Rank", align: "right" as const },
  { key: "team_name", label: "Team", align: "left" as const },
  { key: "GP", label: "GP", align: "right" as const },
  { key: "FG%_Rank", label: "FG%", align: "right" as const },
  { key: "FT%_Rank", label: "FT%", align: "right" as const },
  { key: "3PM_Rank", label: "3PM", align: "right" as const },
  { key: "PTS_Rank", label: "PTS", align: "right" as const },
  { key: "REB_Rank", label: "REB", align: "right" as const },
  { key: "AST_Rank", label: "AST", align: "right" as const },
  { key: "ST_Rank", label: "STL", align: "right" as const },
  { key: "BLK_Rank", label: "BLK", align: "right" as const },
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
    }
  }
];

function toOverallRows(teams: TeamRow[]) {
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

function toOverallStatsRows(teams: TeamRow[]) {
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
  const loader = useCallback((signal: AbortSignal) => getOverview(signal), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  const hasData = Boolean(data?.has_data);
  const leagueId = data?.league_id ?? "";

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
            <DataTable columns={OVERALL_COLUMNS} initialSort={{ key: "rank", desc: false }} rows={toOverallRows(data.teams)} />
          </section>

          <section>
            <h2>Overall Stats</h2>
            <p className="section-note">Raw season totals from Yahoo before per-game normalization.</p>
            <DataTable columns={OVERALL_STATS_COLUMNS} initialSort={{ key: "rank", desc: false }} rows={toOverallStatsRows(data.teams)} />
          </section>

          <section>
            <h2>Per-Game Averages</h2>
            <p className="section-note">Counting stats normalized by games played.</p>
            <DataTable columns={PER_GAME_COLUMNS} initialSort={{ key: "rank", desc: false }} rows={data.per_game_rows} />
          </section>

          <section>
            <h2>Per-Game Category Rankings</h2>
            <p className="section-note">
              Each category ranked 1-10 based on per-game values (10 = best in league). Total is the sum of all category
              ranks. Delta Total is Total minus your actual roto points.
            </p>
            <DataTable columns={RANKING_COLUMNS} initialSort={{ key: "rank_total", desc: true }} rows={data.ranking_rows} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
