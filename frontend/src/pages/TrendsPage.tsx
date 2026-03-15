import { ChangeEvent, useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppShell } from "../components/AppShell";
import { StatusPanel } from "../components/StatusPanel";
import { getTrends } from "../lib/api";
import { formatFixed } from "../lib/format";
import type { TrendsCategoryInfo, TrendsChartPoint, TrendsPayload, TrendsWindowData } from "../lib/types";
import { useAsyncData } from "../lib/useAsyncData";

const TEAM_COLORS = [
  "#1f4fd1", "#d14f1f", "#1fad6b", "#9b1fd1", "#d1a01f",
  "#1f8dd1", "#d11f6b", "#6bd11f", "#d15f1f", "#1fd1c9",
];

const WINDOW_LABELS: Record<string, string> = {
  "1d": "1D",
  "7d": "7D",
  "14d": "14D",
  "30d": "30D",
};

function formatStatValue(value: number | null | undefined, isPct: boolean): string {
  if (value === null || value === undefined) return "—";
  return isPct ? formatFixed(value, 4) : formatFixed(value, 3);
}

function deltaClass(delta: number | null | undefined, higherIsBetter: boolean): string {
  if (delta === null || delta === undefined) return "";
  const effective = higherIsBetter ? delta : -delta;
  if (effective > 0.001) return "trend-positive";
  if (effective < -0.001) return "trend-negative";
  return "";
}

function trendArrow(trend: "up" | "down" | "flat"): string {
  if (trend === "up") return " \u25B2";
  if (trend === "down") return " \u25BC";
  return "";
}

export function TrendsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedTeam = searchParams.get("team") ?? undefined;

  const loader = useCallback(
    (signal: AbortSignal) => getTrends(selectedTeam, signal),
    [selectedTeam],
  );
  const { data, loading, error, reload } = useAsyncData<TrendsPayload>(loader, [selectedTeam]);

  const leagueId = "";
  const hasData = Boolean(data?.has_data);

  // Category selector for chart
  const [selectedCatKey, setSelectedCatKey] = useState<string>("");

  // Team filter for chart
  const [hiddenTeams, setHiddenTeams] = useState<Set<string>>(new Set());

  // Time range filter for chart
  const [timeRange, setTimeRange] = useState<string>("all");

  const categories = data?.categories ?? [];
  const activeCatKey = selectedCatKey || (categories.length > 0 ? categories[0].key : "");
  const activeCat = categories.find((c) => c.key === activeCatKey);

  function onTeamChange(event: ChangeEvent<HTMLSelectElement>) {
    const next = event.target.value;
    const nextParams = new URLSearchParams(searchParams);
    if (next) {
      nextParams.set("team", next);
    } else {
      nextParams.delete("team");
    }
    setSearchParams(nextParams);
  }

  // Build chart data for recharts
  const teamNames = data?.team_names ?? [];
  const chartData = useMemo(() => {
    if (!data?.chart_data || !activeCatKey) return [];

    // Filter by time range
    let points = data.chart_data;
    if (timeRange !== "all" && points.length > 0) {
      const days = parseInt(timeRange, 10);
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - days);
      const cutoffStr = cutoff.toISOString().slice(0, 10);
      points = points.filter((p: TrendsChartPoint) => p.date >= cutoffStr);
    }

    return points.map((point: TrendsChartPoint) => {
      const row: Record<string, string | number | null> = { date: point.date };
      for (const team of teamNames) {
        if (!hiddenTeams.has(team)) {
          const val = point.teams?.[team]?.[activeCatKey] ?? null;
          row[team] = val;
        }
      }
      return row;
    });
  }, [data?.chart_data, activeCatKey, teamNames, hiddenTeams, timeRange]);

  function toggleTeam(name: string) {
    setHiddenTeams((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  function showAllTeams() {
    setHiddenTeams(new Set());
  }

  function hideAllTeams() {
    setHiddenTeams(new Set(teamNames));
  }

  return (
    <AppShell leagueId={leagueId} loading={loading} onReload={reload} scrapedAt={null}>
      <StatusPanel
        emptyMessage="No trends data yet. Refresh your standings daily to build up time series data."
        error={error}
        hasData={hasData}
        loading={loading}
      />

      {!hasData && data && !loading && (
        <section className="trends-empty-state">
          <div className="section-note">
            <strong>Building your trends data</strong>
            <p>
              Time series analysis requires at least 2 days of snapshots. Each time you refresh
              standings, a snapshot is saved automatically. Come back after refreshing on a second day
              to see your trends.
            </p>
            {data.snapshot_coverage && (
              <p>
                First snapshot: <strong>{data.snapshot_coverage.first_date}</strong>
                {" | "}Snapshots collected: <strong>{data.snapshot_coverage.total_snapshots}</strong>
              </p>
            )}
          </div>
        </section>
      )}

      {hasData && data && (
        <>
          {/* ── Scorecard Section ── */}
          <section>
            <h2>Trends & Scorecard</h2>
            <div className="control-row">
              <label htmlFor="trends-team-select">Select Team</label>
              <select id="trends-team-select" onChange={onTeamChange} value={data.selected_team ?? ""}>
                {data.team_names.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>

            {data.snapshot_coverage && (
              <p className="section-note" style={{ marginTop: 8 }}>
                Data from <strong>{data.snapshot_coverage.first_date}</strong> to{" "}
                <strong>{data.snapshot_coverage.last_date}</strong>
                {" "}({data.snapshot_coverage.total_snapshots} snapshots)
              </p>
            )}

            {data.scorecard && (
              <div className="table-wrap" style={{ marginTop: 16 }}>
                <table>
                  <thead>
                    <tr>
                      <th className="align-left">Category</th>
                      {Object.keys(WINDOW_LABELS).map((wk) => (
                        <th key={wk}>{WINDOW_LABELS[wk]}</th>
                      ))}
                      <th>Season Avg</th>
                      <th>Leader Avg</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.map((cat: TrendsCategoryInfo) => {
                      const seasonAvg = data.season_averages?.[data.selected_team ?? ""]?.[cat.key];
                      // Find the league leader's season average for this category
                      let leaderValue: number | null = null;
                      let leaderTeam: string | null = null;
                      if (data.season_averages) {
                        for (const [teamName, avgs] of Object.entries(data.season_averages)) {
                          const val = avgs[cat.key];
                          if (val == null) continue;
                          if (leaderValue === null ||
                            (cat.higher_is_better ? val > leaderValue : val < leaderValue)) {
                            leaderValue = val;
                            leaderTeam = teamName;
                          }
                        }
                      }
                      return (
                        <tr key={cat.key}>
                          <td className="align-left" style={{ fontWeight: 500 }}>{cat.display}</td>
                          {Object.keys(WINDOW_LABELS).map((wk) => {
                            const window: TrendsWindowData | undefined = data.scorecard?.windows[wk];
                            if (!window?.available) {
                              return <td key={wk} style={{ color: "var(--muted)" }}>—</td>;
                            }
                            const stat = window.categories[cat.key];
                            if (!stat || stat.value === null) {
                              return <td key={wk} style={{ color: "var(--muted)" }}>—</td>;
                            }
                            const cls = deltaClass(stat.vs_own_avg, cat.higher_is_better);
                            return (
                              <td key={wk} className={cls}>
                                {formatStatValue(stat.value, cat.is_percentage)}
                                {stat.vs_own_avg !== null && (
                                  <span className="trend-delta">
                                    {" "}({stat.vs_own_avg > 0 ? "+" : ""}{formatStatValue(stat.vs_own_avg, cat.is_percentage)})
                                  </span>
                                )}
                                <span className="trend-arrow">{trendArrow(stat.trend)}</span>
                              </td>
                            );
                          })}
                          <td style={{ color: "var(--muted)" }}>
                            {formatStatValue(seasonAvg, cat.is_percentage)}
                          </td>
                          <td>
                            {leaderValue != null ? (
                              <span title={leaderTeam ?? ""}>
                                {formatStatValue(leaderValue, cat.is_percentage)}
                              </span>
                            ) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* ── Chart Section ── */}
          {data.chart_data && data.chart_data.length > 0 && (
            <section style={{ marginTop: 24 }}>
              <h2>Time Series</h2>
              <div className="trends-chart-controls">
                <span>
                  <label htmlFor="trends-cat-select">Category</label>
                  <select
                    id="trends-cat-select"
                    value={activeCatKey}
                    onChange={(e) => setSelectedCatKey(e.target.value)}
                  >
                    {categories.map((cat) => (
                      <option key={cat.key} value={cat.key}>{cat.display}</option>
                    ))}
                  </select>
                </span>
                <span>
                  <label htmlFor="trends-range-select">Time Range</label>
                  <select
                    id="trends-range-select"
                    value={timeRange}
                    onChange={(e) => setTimeRange(e.target.value)}
                  >
                    <option value="all">All Time</option>
                    <option value="7">Last 7 Days</option>
                    <option value="14">Last 14 Days</option>
                    <option value="30">Last 30 Days</option>
                    <option value="60">Last 60 Days</option>
                  </select>
                </span>
              </div>

              <div className="trends-team-filter" style={{ marginBottom: 12 }}>
                <span style={{ fontSize: 12, fontWeight: 500, marginRight: 8 }}>Teams:</span>
                <button
                  type="button"
                  className="ghost"
                  style={{ fontSize: 11, padding: "2px 6px", marginRight: 4 }}
                  onClick={showAllTeams}
                >
                  All
                </button>
                <button
                  type="button"
                  className="ghost"
                  style={{ fontSize: 11, padding: "2px 6px", marginRight: 8 }}
                  onClick={hideAllTeams}
                >
                  None
                </button>
                {teamNames.map((name, i) => (
                  <label
                    key={name}
                    style={{
                      fontSize: 11,
                      marginRight: 8,
                      cursor: "pointer",
                      opacity: hiddenTeams.has(name) ? 0.4 : 1,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={!hiddenTeams.has(name)}
                      onChange={() => toggleTeam(name)}
                      style={{ marginRight: 3 }}
                    />
                    <span style={{ color: TEAM_COLORS[i % TEAM_COLORS.length] }}>
                      {name}
                    </span>
                  </label>
                ))}
              </div>

              <div className="trends-chart-wrap">
                <ResponsiveContainer>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(d: string) => {
                        const parts = d.split("-");
                        return `${parts[1]}/${parts[2]}`;
                      }}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      domain={["auto", "auto"]}
                      tickFormatter={(v: number) =>
                        activeCat?.is_percentage ? formatFixed(v, 4) : formatFixed(v, 3)
                      }
                    />
                    <Tooltip
                      formatter={(value: unknown) => {
                        const num = typeof value === "number" ? value : 0;
                        return activeCat?.is_percentage
                          ? formatFixed(num, 4)
                          : formatFixed(num, 3);
                      }}
                      labelFormatter={(label: unknown) => `Date: ${String(label)}`}
                    />
                    <Legend />
                    {teamNames
                      .filter((name) => !hiddenTeams.has(name))
                      .map((name, i) => (
                        <Line
                          key={name}
                          type="monotone"
                          dataKey={name}
                          name={name}
                          stroke={TEAM_COLORS[i % TEAM_COLORS.length]}
                          strokeWidth={name === data.selected_team ? 3 : 1.5}
                          dot={false}
                          connectNulls
                        />
                      ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}
        </>
      )}
    </AppShell>
  );
}
