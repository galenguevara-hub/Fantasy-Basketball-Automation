import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getGamesPlayed } from "../lib/api";
import { formatFixed, toNumber } from "../lib/format";
import { useAsyncData } from "../lib/useAsyncData";
import type { CountingCategoryMeta, JsonRecord } from "../lib/types";
import type { ReactNode } from "react";

const GAMES_COLUMNS = [
  { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "rank", label: "Rank", align: "right" as const },
  { key: "gp", label: "GP", align: "right" as const },
  { key: "rank_total", label: "PG Total", align: "right" as const },
  { key: "avg_gp_per_day_so_far", label: "GP/Day So Far", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  {
    key: "avg_gp_per_day_needed",
    label: "GP/Day Remaining",
    align: "right" as const,
    render: (value: unknown) => formatFixed(value, 2)
  },
  {
    key: "net_rate_delta",
    label: "Net Delta",
    align: "right" as const,
    render: (value: unknown) => {
      const num = toNumber(value);
      if (num === null) {
        return "—";
      }
      const klass = num > 0 ? "delta delta-behind" : num < 0 ? "delta delta-ahead" : "delta";
      const display = `${num > 0 ? "+" : ""}${num.toFixed(2)}`;
      return <span className={klass}>{display}</span>;
    }
  }
];

function formatDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-");
  if (!year || !month || !day) return dateStr;
  return `${month}/${day}/${year}`;
}

function formatWhole(value: unknown): ReactNode {
  const num = toNumber(value);
  if (num === null) return "—";
  return num.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function buildProjectedTotalsColumns(
  categories: CountingCategoryMeta[],
  maxGpTeams: Set<string>,
  onToggle: (teamName: string) => void,
) {
  return [
    { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
    {
      key: "__max_gp",
      label: "Max GP?",
      align: "center" as const,
      render: (_value: unknown, row: JsonRecord) => (
        <input
          checked={maxGpTeams.has(row.team_name as string)}
          onChange={() => onToggle(row.team_name as string)}
          type="checkbox"
        />
      ),
      sortValue: (_value: unknown, row: JsonRecord) => (maxGpTeams.has(row.team_name as string) ? 1 : 0),
    },
    { key: "projected_gp", label: "Proj GP", align: "right" as const, render: formatWhole },
    ...categories.map((cat) => ({
      key: `projected_${cat.key}`,
      label: cat.display,
      align: "right" as const,
      render: formatWhole,
    })),
  ];
}

function buildProjectedRanksColumns(categories: CountingCategoryMeta[]) {
  const countingColumns = categories.map((cat) => ({
    key: `${cat.key}_Rank`,
    label: cat.display,
    align: "right" as const,
  }));

  return [
    { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
    { key: "projected_gp", label: "Proj GP", align: "right" as const, render: formatWhole },
    { key: "FG%_Rank", label: "FG%", align: "right" as const },
    { key: "FT%_Rank", label: "FT%", align: "right" as const },
    ...countingColumns,
    {
      key: "projected_total",
      label: "Total",
      align: "right" as const,
      cellClassName: "col-total",
      render: (value: unknown) => {
        const num = toNumber(value);
        if (num === null) return "—";
        // Show .5 for half-ranks from Yahoo tie averaging, whole numbers otherwise
        return Number.isInteger(num) ? String(num) : num.toFixed(1);
      },
    },
  ];
}

/** Recompute projected totals for teams with Max GP toggled on. */
function adjustTotals(
  rows: JsonRecord[],
  maxGpTeams: Set<string>,
  totalGames: number,
  categories: CountingCategoryMeta[],
): JsonRecord[] {
  if (maxGpTeams.size === 0) return rows;
  return rows.map((row) => {
    const name = row.team_name as string;
    if (!maxGpTeams.has(name)) return row;
    const origGp = toNumber(row.projected_gp);
    if (!origGp || origGp === 0) return row;
    const adjusted: JsonRecord = { ...row, projected_gp: totalGames };
    for (const cat of categories) {
      const origVal = toNumber(row[`projected_${cat.key}`]);
      if (origVal !== null) {
        adjusted[`projected_${cat.key}`] = Math.round((origVal / origGp) * totalGames);
      }
    }
    return adjusted;
  });
}

/** Re-rank teams based on adjusted projected totals. Matches backend algorithm. */
function rerankTeams(
  adjustedTotals: JsonRecord[],
  originalRanks: JsonRecord[],
  categories: CountingCategoryMeta[],
): JsonRecord[] {
  const nTeams = adjustedTotals.length;
  if (nTeams === 0) return [];

  // Build lookup for FG%/FT% ranks from original data (unchanged)
  const origRanksByName: Record<string, JsonRecord> = {};
  for (const r of originalRanks) {
    origRanksByName[r.team_name as string] = r;
  }

  // Rank each counting category: higher value = higher rank (N = best)
  const countingKeys = categories.map((cat) => `projected_${cat.key}`);
  const rankings: Record<string, Record<string, number>> = {};
  for (const r of adjustedTotals) {
    rankings[r.team_name as string] = {};
  }

  for (const projKey of countingKeys) {
    const entries: [string, number | null][] = adjustedTotals.map((r) => [
      r.team_name as string,
      toNumber(r[projKey]),
    ]);

    // Sort: null sinks to end (rank 1), higher value first (rank N)
    entries.sort((a, b) => {
      const [nameA, valA] = a;
      const [nameB, valB] = b;
      if (valA === null && valB === null) return nameA.localeCompare(nameB);
      if (valA === null) return 1;
      if (valB === null) return -1;
      if (valB !== valA) return valB - valA;
      return nameA.localeCompare(nameB);
    });

    for (let i = 0; i < entries.length; i++) {
      const [name] = entries[i];
      rankings[name][projKey] = nTeams - i;
    }
  }

  // Build output rows
  return adjustedTotals.map((r) => {
    const name = r.team_name as string;
    const rankData = rankings[name] ?? {};
    const orig = origRanksByName[name] ?? {};

    const row: JsonRecord = {
      team_name: name,
      rank: r.rank,
      projected_gp: r.projected_gp,
    };

    const catRankSum: number[] = [];
    for (const cat of categories) {
      const projKey = `projected_${cat.key}`;
      const rankVal = rankData[projKey] ?? null;
      row[`${cat.key}_Rank`] = rankVal;
      if (rankVal !== null) catRankSum.push(rankVal);
    }

    // Carry FG%/FT% from original ranks
    const fgRank = toNumber(orig["FG%_Rank"]);
    const ftRank = toNumber(orig["FT%_Rank"]);
    row["FG%_Rank"] = fgRank;
    row["FT%_Rank"] = ftRank;
    if (fgRank !== null) catRankSum.push(fgRank);
    if (ftRank !== null) catRankSum.push(ftRank);

    row.projected_total = catRankSum.length > 0 ? catRankSum.reduce((a, b) => a + b, 0) : null;
    return row;
  });
}

export function GamesPlayedPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const startParam = searchParams.get("start") || undefined;
  const endParam = searchParams.get("end") || undefined;
  const totalGamesParam = searchParams.get("total_games") || undefined;
  const [form, setForm] = useState({ start: "", end: "", totalGames: "" });

  const loader = useCallback(
    (signal: AbortSignal) =>
      getGamesPlayed({
        start: startParam,
        end: endParam,
        totalGames: totalGamesParam,
        signal
      }),
    [endParam, startParam, totalGamesParam]
  );

  const { data, loading, error, reload } = useAsyncData(loader, [startParam, endParam, totalGamesParam]);

  const hasData = Boolean(data?.has_data);
  const leagueId = data?.league_id ?? "";

  useEffect(() => {
    if (!data) return;
    setForm({
      start: startParam ?? data.start_str,
      end: endParam ?? data.end_str,
      totalGames: totalGamesParam ?? String(data.total_games)
    });
  }, [data, endParam, startParam, totalGamesParam]);

  const categories = data?.counting_categories ?? [];

  // Max GP toggle state — per-team set, reset when data reloads
  const [maxGpTeams, setMaxGpTeams] = useState<Set<string>>(new Set());
  useEffect(() => { setMaxGpTeams(new Set()); }, [data]);

  const toggleMaxGp = useCallback((teamName: string) => {
    setMaxGpTeams((prev) => {
      const next = new Set(prev);
      if (next.has(teamName)) next.delete(teamName);
      else next.add(teamName);
      return next;
    });
  }, []);

  // Adjusted projections when Max GP is toggled
  const adjustedTotals = useMemo(
    () => adjustTotals(data?.projected_totals ?? [], maxGpTeams, data?.total_games ?? 816, categories),
    [data?.projected_totals, maxGpTeams, data?.total_games, categories],
  );
  const adjustedRanks = useMemo(
    () => rerankTeams(adjustedTotals, data?.projected_ranks ?? [], categories),
    [adjustedTotals, data?.projected_ranks, categories],
  );

  const projTotalsColumns = useMemo(
    () => buildProjectedTotalsColumns(categories, maxGpTeams, toggleMaxGp),
    [categories, maxGpTeams, toggleMaxGp],
  );
  const projRanksColumns = useMemo(() => buildProjectedRanksColumns(categories), [categories]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextParams = new URLSearchParams(searchParams);
    if (form.start) nextParams.set("start", form.start);
    else nextParams.delete("start");
    if (form.end) nextParams.set("end", form.end);
    else nextParams.delete("end");
    if (form.totalGames) nextParams.set("total_games", form.totalGames);
    else nextParams.delete("total_games");
    setSearchParams(nextParams);
  }

  return (
    <AppShell leagueId={leagueId} loading={loading} onReload={reload} scrapedAt={data?.scraped_at ?? null}>
      <StatusPanel
        emptyMessage="No standings data yet. Go to Standings and run a refresh first."
        error={error}
        hasData={hasData}
        loading={loading}
      />

      {hasData && data ? (
        <>
          <section>
            <h2>Season Window</h2>
            <form className="gp-form" onSubmit={onSubmit}>
              <div className="gp-row">
                <label htmlFor="start">Start</label>
                <input
                  id="start"
                  onChange={(event) => setForm((prev) => ({ ...prev, start: event.target.value }))}
                  type="date"
                  value={form.start}
                />
                <label htmlFor="end">End</label>
                <input
                  id="end"
                  onChange={(event) => setForm((prev) => ({ ...prev, end: event.target.value }))}
                  type="date"
                  value={form.end}
                />
              </div>
              <div className="gp-row">
                <label htmlFor="total-games">Total games</label>
                <input
                  className="gp-total-input"
                  id="total-games"
                  min={1}
                  onChange={(event) => setForm((prev) => ({ ...prev, totalGames: event.target.value }))}
                  type="number"
                  value={form.totalGames}
                />
                <button type="submit">Update</button>
              </div>
            </form>

            {data.date_error ? <p className="panel error">{data.date_error}</p> : null}
            {data.date_valid ? (
              <p className="section-note">
                <strong>{data.elapsed_days}</strong> days elapsed · <strong>{data.remaining_days}</strong> days remaining (
                {formatDate(data.start_str)} - {formatDate(data.end_str)}, inclusive)
              </p>
            ) : null}
          </section>

          <section>
            <h2>Games Played Pace</h2>
            <DataTable columns={GAMES_COLUMNS} initialSort={{ key: "rank", desc: false }} rows={data.rows} />
            <p className="section-note gp-key">
              <strong>GP/Day So Far</strong> - games played / elapsed days
              <br />
              <strong>GP/Day Remaining</strong> - (total games - GP) / remaining days: how many games per day you still
              need to play
              <br />
              <strong>Net Delta</strong> - GP/Day Remaining - GP/Day So Far: positive = need to speed up, negative = can
              slow down
            </p>
          </section>

          {data.projected_totals.length > 0 ? (
            <>
              <section>
                <h2>Projected End-of-Season Counting Totals</h2>
                <p className="section-note gp-key">
                  Extrapolates each team's current GP/day pace through the season end, capped at {data.total_games} total games.
                  Per-game averages are multiplied by projected total GP to estimate final counting stats.
                </p>
                <DataTable
                  columns={projTotalsColumns}
                  initialSort={{ key: "projected_gp", desc: true }}
                  rows={adjustedTotals}
                />
              </section>

              <section>
                <h2>Projected End-of-Season Roto Rankings</h2>
                <p className="section-note gp-key">
                  Counting-stat ranks are based on projected totals above. FG% and FT% ranks are carried forward
                  from Yahoo's current base rankings. Total is the sum of all 8 category ranks.
                </p>
                <DataTable
                  columns={projRanksColumns}
                  initialSort={{ key: "projected_total", desc: true }}
                  rows={adjustedRanks}
                />
              </section>
            </>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
