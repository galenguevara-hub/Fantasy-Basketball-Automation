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
  return isPct ? (value * 100).toFixed(1) + "%" : formatFixed(value, 1);
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
    return data.chart_data.map((point: TrendsChartPoint) => {
      const row: Record<string, string | number | null> = { date: point.date };
      for (const team of teamNames) {
        if (!hiddenTeams.has(team)) {
          const val = point.teams?.[team]?.[activeCatKey] ?? null;
          row[team] = val;
        }
      }
      return row;
    });
  }, [data?.chart_data, activeCatKey, teamNames, hiddenTeams]);

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
              <div className="trends-scorecard-table" style={{ overflowX: "auto", marginTop: 16 }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left" }}>Category</th>
                      {Object.keys(WINDOW_LABELS).map((wk) => (
                        <th key={wk} style={{ textAlign: "right" }}>{WINDOW_LABELS[wk]}</th>
                      ))}
                      <th style={{ textAlign: "right" }}>Season Avg</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.map((cat: TrendsCategoryInfo) => {
                      const seasonAvg = data.season_averages?.[data.selected_team ?? ""]?.[cat.key];
                      return (
                        <tr key={cat.key}>
                          <td style={{ textAlign: "left", fontWeight: 500 }}>{cat.display}</td>
                          {Object.keys(WINDOW_LABELS).map((wk) => {
                            const window: TrendsWindowData | undefined = data.scorecard?.windows[wk];
                            if (!window?.available) {
                              return <td key={wk} style={{ textAlign: "right", color: "var(--muted)" }}>—</td>;
                            }
                            const stat = window.categories[cat.key];
                            if (!stat || stat.value === null) {
                              return <td key={wk} style={{ textAlign: "right", color: "var(--muted)" }}>—</td>;
                            }
                            const cls = deltaClass(stat.vs_own_avg, cat.higher_is_better);
                            return (
                              <td key={wk} style={{ textAlign: "right" }} className={cls}>
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
                          <td style={{ textAlign: "right", color: "var(--muted)" }}>
                            {formatStatValue(seasonAvg, cat.is_percentage)}
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
              <div className="control-row" style={{ marginBottom: 16 }}>
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

              <div style={{ width: "100%", height: 400 }}>
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
                        activeCat?.is_percentage ? (v * 100).toFixed(0) + "%" : v.toFixed(1)
                      }
                    />
                    <Tooltip
                      formatter={(value: unknown) => {
                        const num = typeof value === "number" ? value : 0;
                        return activeCat?.is_percentage
                          ? (num * 100).toFixed(1) + "%"
                          : num.toFixed(2);
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
