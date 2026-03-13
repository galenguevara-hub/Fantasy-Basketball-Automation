import { ChangeEvent, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getExecutiveSummary } from "../lib/api";
import { formatCompact, formatFixed, formatSigned, toNumber } from "../lib/format";
import type { JsonRecord } from "../lib/types";
import { useAsyncData } from "../lib/useAsyncData";

const CAT_CLASS_MAP: Record<string, string> = {
  "FG%": "cat-fg",
  "FT%": "cat-ft",
  "3PM": "cat-3pm",
  "3PM/G": "cat-3pm",
  "3PT%": "cat-3pt",
  "PTS": "cat-pts",
  "PTS/G": "cat-pts",
  "REB": "cat-reb",
  "REB/G": "cat-reb",
  "AST": "cat-ast",
  "AST/G": "cat-ast",
  "STL": "cat-stl",
  "STL/G": "cat-stl",
  "BLK": "cat-blk",
  "BLK/G": "cat-blk",
  "TO": "cat-to",
  "TO/G": "cat-to",
};

function getCatClass(category: string): string {
  if (CAT_CLASS_MAP[category]) return CAT_CLASS_MAP[category];
  const slug = category.toLowerCase().replace(/[^a-z0-9]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  return `cat-${slug}`;
}

function asRows(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? (value as JsonRecord[]) : [];
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function formatGap(value: unknown): string {
  const num = toNumber(value);
  return num === null ? "—" : num.toFixed(2);
}

function formatOrdinal(value: unknown): string {
  const num = toNumber(value);
  if (num === null) return "—";
  const rank = Math.round(num);
  const mod100 = rank % 100;
  const suffix = mod100 >= 11 && mod100 <= 13 ? "th" : rank % 10 === 1 ? "st" : rank % 10 === 2 ? "nd" : rank % 10 === 3 ? "rd" : "th";
  return `${rank}${suffix}`;
}

function renderCategoryChip(label: string, key: string) {
  return (
    <span key={key} className={`tag ${getCatClass(label)}`}>
      {label.replace("/G", "")}
    </span>
  );
}

function renderTeamChip(label: string, key: string) {
  return (
    <span key={key} className="tag team-chip">
      {label}
    </span>
  );
}

function renderIntensity(value: unknown) {
  const text = asText(value);
  const klass =
    text === "High"
      ? "intensity intensity-high"
      : text === "Medium"
      ? "intensity intensity-medium"
      : text === "Low"
      ? "intensity intensity-low"
      : "intensity intensity-minimal";
  return <span className={klass}>{text || "Minimal"}</span>;
}

function renderRoiCategory(value: unknown) {
  const text = asText(value);
  const klass =
    text === "High"
      ? "roi-chip roi-high"
      : text === "Medium"
      ? "roi-chip roi-medium"
      : "roi-chip roi-low";
  return <span className={klass}>{text || "Low"}</span>;
}

function renderStability(value: unknown) {
  const text = asText(value);
  const lower = text.toLowerCase();
  const klass =
    lower === "stable"
      ? "stability-chip stability-stable"
      : lower === "moderate"
      ? "stability-chip stability-moderate"
      : lower === "unstable"
      ? "stability-chip stability-unstable"
      : "stability-chip stability-unknown";
  return <span className={klass}>{text || "Unknown"}</span>;
}

function renderCompetitorChips(value: unknown) {
  const names = asStringArray(value);
  if (names.length === 0) {
    return <span className="muted-inline">minimal overlap</span>;
  }
  return (
    <div className="tag-list">
      {names.map((name) => (
        <span key={name} className="tag competitor-chip">
          {name}
        </span>
      ))}
    </div>
  );
}

const PER_GAME_VS_RAW_COLUMNS = [
  { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "raw_roto_rank", label: "Raw Roto Rank", align: "right" as const, render: (value: unknown) => formatOrdinal(value) },
  { key: "per_game_rank", label: "Per-Game Rank", align: "right" as const, render: (value: unknown) => formatOrdinal(value) },
  {
    key: "difference",
    label: "Difference",
    align: "right" as const,
    render: (value: unknown) => {
      const num = toNumber(value);
      if (num === null) return "—";
      const sign = num > 0 ? "+" : "";
      const klass = num > 0 ? "diff diff-positive" : num < 0 ? "diff diff-negative" : "diff diff-neutral";
      return <span className={klass}>{`${sign}${num.toFixed(0)}`}</span>;
    },
  },
];

const CATEGORY_OPPORTUNITY_COLUMNS = [
  { key: "category", label: "Category", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "gap_to_gain_1", label: "Gap to Gain 1", align: "right" as const, render: formatGap },
  { key: "gap_to_lose_1", label: "Gap to Lose 1", align: "right" as const, render: formatGap },
  { key: "roi_score", label: "ROI Category", align: "center" as const, render: renderRoiCategory },
  { key: "leverage_score", label: "Leverage", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
];

const MULTI_SWING_COLUMNS = [
  { key: "category", label: "Category", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "potential_swing", label: "Potential Swing", align: "right" as const, render: (value: unknown) => formatCompact(value, 0) },
  { key: "full_swing_text", label: "Improvement for Full Swing", align: "right" as const },
  { key: "headline", label: "Summary", align: "left" as const },
];

const NEARBY_COLUMNS = [
  { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "per_game_rank", label: "Per-Game Rank", align: "right" as const, render: (value: unknown) => formatOrdinal(value) },
  { key: "games_played", label: "Games Played", align: "right" as const, render: (value: unknown) => formatCompact(value, 0) },
  { key: "projected_gp", label: "Projected GP", align: "right" as const, render: (value: unknown) => formatCompact(value, 0) },
];

const PROJECTED_COLUMNS = [
  { key: "team_name", label: "Team", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "current_points", label: "Current Points", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  { key: "projected_points", label: "Projected Points", align: "right" as const, render: (value: unknown) => formatCompact(value, 1) },
  {
    key: "points_diff",
    label: "Difference",
    align: "right" as const,
    render: (value: unknown) => {
      const num = toNumber(value);
      if (num === null) return "—";
      const sign = num > 0 ? "+" : "";
      const klass = num > 0 ? "diff diff-positive" : num < 0 ? "diff diff-negative" : "diff diff-neutral";
      return <span className={klass}>{`${sign}${num.toFixed(1)}`}</span>;
    },
  },
  { key: "current_rank", label: "Current Rank", align: "right" as const, render: (value: unknown) => formatOrdinal(value) },
  { key: "projected_rank", label: "Projected Rank", align: "right" as const, render: (value: unknown) => formatOrdinal(value) },
];

const COMPETITION_COLUMNS = [
  { key: "category", label: "Category", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "intensity", label: "Competition", align: "center" as const, render: renderIntensity },
  { key: "competitors", label: "Nearby Competitors", align: "left" as const, render: renderCompetitorChips },
];

const STABILITY_COLUMNS = [
  { key: "category", label: "Category", align: "left" as const, headerClassName: "col-team", cellClassName: "col-team" },
  { key: "sigma", label: "Std Dev", align: "right" as const, render: (value: unknown, row: Record<string, unknown>) => {
    const cat = row.category;
    return formatFixed(value, cat === "FG%" || cat === "FT%" ? 4 : 3);
  } },
  { key: "volatility", label: "Stability", align: "center" as const, render: renderStability },
];

export function ExecutiveSummaryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTeam = searchParams.get("team")?.trim() || undefined;
  const loader = useCallback((signal: AbortSignal) => getExecutiveSummary(requestedTeam, signal), [requestedTeam]);
  const { data, loading, error, reload } = useAsyncData(loader, [requestedTeam]);

  const hasData = Boolean(data?.has_data);
  const leagueId = data?.league_id ?? "";

  const summaryCard = (data?.summary_card ?? {}) as JsonRecord;
  const opportunities = asRows(summaryCard.opportunities);
  const risks = asRows(summaryCard.risks);

  const gamesPace = (data?.games_pace ?? {}) as JsonRecord;
  const currentPace = gamesPace.current_pace;
  const projectedFinal = gamesPace.projected_final_games_played;
  const projectedDeltaVsAvg = toNumber(gamesPace.projected_gp_delta_vs_avg);
  const recommendedAdjustment = gamesPace.recommended_pace_adjustment;
  const remainingDays = gamesPace.remaining_days;
  const neededRateToCap = gamesPace.needed_gp_per_day_to_hit_cap;

  const selectedVsRawRow = asRows(data?.per_game_vs_raw_rows).find((row) => Boolean(row.is_selected));
  const nearbyTeams = asRows(data?.nearby_teams);
  const nearbyCompetitors = nearbyTeams.filter((row) => !row.is_selected).map((row) => asText(row.team_name));
  const highLeverageCats = asStringArray(data?.high_leverage_categories);

  const projectedRowsWithDiff = asRows(data?.projected_standings).map((row) => {
    const current = toNumber(row.current_points);
    const projected = toNumber(row.projected_points);
    return {
      ...row,
      points_diff: current !== null && projected !== null ? projected - current : null,
    };
  });

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
            <h2>Executive Summary</h2>
            <div className="control-row">
              <label htmlFor="executive-team-select">Select Your Team</label>
              <select id="executive-team-select" onChange={onTeamChange} value={data.selected_team ?? ""}>
                {data.team_names.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            <div className="executive-metrics-grid executive-top-metrics">
              <div className="metric-card">
                <span className="metric-label">Current Rank</span>
                <strong className="dyn-value">{formatOrdinal(selectedVsRawRow?.raw_roto_rank)}</strong>
              </div>
              <div className="metric-card">
                <span className="metric-label">Per-Game Rank</span>
                <strong className="dyn-value">{formatOrdinal(selectedVsRawRow?.per_game_rank)}</strong>
              </div>

              <div className="metric-card">
                <span className="metric-label">Current Roto Pts</span>
                <strong className="dyn-value">{formatCompact(selectedVsRawRow?.current_points, 1)}</strong>
              </div>
              <div className="metric-card">
                <span className="metric-label">EQUAL GAMES PLAYED RANK</span>
                <strong className="dyn-value">{formatOrdinal(summaryCard.expected_equal_gp_rank)}</strong>
              </div>
            </div>

            <div className="panel executive-card">
              <p className="executive-line">
                Position <strong className="dyn-value">{formatOrdinal(selectedVsRawRow?.raw_roto_rank)}</strong> now vs{" "}
                <strong className="dyn-value">{formatOrdinal(selectedVsRawRow?.per_game_rank)}</strong> on equal GP.
              </p>
              <p className="executive-line">
                Closest teams:{" "}
                <span className="insight-chip-wrap">
                  {nearbyCompetitors.map((teamName, idx) => renderTeamChip(teamName, `nearby-${idx}`))}
                </span>
              </p>
              {highLeverageCats.length > 0 ? (
                <p className="executive-line">
                  High-leverage categories:{" "}
                  <span className="insight-chip-wrap">
                    {highLeverageCats.map((cat, idx) => renderCategoryChip(cat, `hl-${idx}`))}
                  </span>
                </p>
              ) : null}

              <div className="executive-buckets">
                <div>
                  <h3>Biggest Opportunities</h3>
                  <ul className="executive-list">
                    {opportunities.map((row, idx) => (
                      <li key={`opportunity-${idx}`}>
                        {renderCategoryChip(asText(row.category), `op-${idx}`)}{" "}
                        <strong className="dyn-value">{formatGap(row.gap_to_gain_1)}</strong> to gain 1 point
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h3>Biggest Risks</h3>
                  <ul className="executive-list">
                    {risks.map((row, idx) => (
                      <li key={`risk-${idx}`}>
                        {renderCategoryChip(asText(row.category), `risk-${idx}`)}{" "}
                        <strong className="dyn-value">{formatGap(row.gap_to_lose_1)}</strong> buffer
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <p className="executive-line">
                <strong className="dyn-value">{formatCompact(remainingDays, 0)} days left</strong> - prioritize category
                clusters with the highest swing potential first.
              </p>
            </div>
          </section>

          <section>
            <h2>Per-Game vs Raw Standings</h2>
            <DataTable
              columns={PER_GAME_VS_RAW_COLUMNS}
              initialSort={{ key: "per_game_rank", desc: false }}
              rows={data.per_game_vs_raw_rows}
              rowClassName={(row) => (row.is_selected ? "row-selected" : undefined)}
            />
            {data.per_game_vs_raw_label ? <p className="section-note">{data.per_game_vs_raw_label}</p> : null}
          </section>

          <section>
            <h2>Category Gain / Loss Opportunities</h2>
            <DataTable
              columns={CATEGORY_OPPORTUNITY_COLUMNS}
              initialSort={{ key: "leverage_score", desc: true }}
              rows={data.category_opportunities}
            />
          </section>

          <section>
            <h2>Multi-Point Swing Opportunities</h2>
            <DataTable columns={MULTI_SWING_COLUMNS} initialSort={{ key: "potential_swing", desc: true }} rows={data.multi_point_swings} />
          </section>

          <section>
            <h2>Games Played Pace</h2>
            <div className="executive-metrics-grid">
              <div className="metric-card">
                <span className="metric-label">Current pace</span>
                <strong className="dyn-value">{formatFixed(currentPace, 2)} GP/day</strong>
              </div>
              <div className="metric-card">
                <span className="metric-label">Projected final</span>
                <strong className="dyn-value">{formatCompact(projectedFinal, 0)} games</strong>
              </div>
              <div className="metric-card">
                <span className="metric-label">Needed pace to cap</span>
                <strong className="dyn-value">{formatFixed(neededRateToCap, 2)} GP/day</strong>
              </div>
              <div className="metric-card">
                <span className="metric-label">Recommended delta</span>
                <strong className="dyn-value">+{formatFixed(recommendedAdjustment, 2)} GP/day</strong>
              </div>
            </div>
            <p className="section-note">
              <strong className="dyn-value">{formatCompact(remainingDays, 0)} days left</strong> - with limited runway,
              prioritize categories with the largest cluster swing first.
            </p>
            {projectedDeltaVsAvg !== null ? (
              <p className="section-note">Projected GP vs league average: <strong className="dyn-value">{formatSigned(projectedDeltaVsAvg, 0)}</strong></p>
            ) : null}
          </section>

          <section>
            <h2>Games Played vs Nearby Teams</h2>
            <DataTable
              columns={NEARBY_COLUMNS}
              initialSort={{ key: "per_game_rank", desc: false }}
              rows={data.nearby_teams}
              rowClassName={(row) => (row.is_selected ? "row-selected" : undefined)}
            />
          </section>

          <section>
            <h2>Projected Final Standings</h2>
            <DataTable
              columns={PROJECTED_COLUMNS}
              initialSort={{ key: "projected_points", desc: true }}
              rows={projectedRowsWithDiff}
              rowClassName={(row) => (row.is_selected ? "row-selected" : undefined)}
            />
          </section>

          <section>
            <h2>Category Competition Map</h2>
            <DataTable columns={COMPETITION_COLUMNS} initialSort={{ key: "intensity_score", desc: true }} rows={data.category_competition} />
            <p className="section-note">
              Method: Nearby teams are the 3 closest per-game ranks; competition intensity is based on category rank overlap
              within 2 spots.
            </p>
          </section>

          <section>
            <h2>Category Stability Indicator</h2>
            <DataTable columns={STABILITY_COLUMNS} initialSort={{ key: "sigma", desc: true }} rows={data.category_stability} />
          </section>

          <section>
            <h2>Actionable Insights</h2>
            <ol className="executive-list executive-list-numbered">
              {asRows(data.actionable_insights).map((insight, idx) => {
                const categories = asStringArray(insight.categories);
                const metric = asText(insight.metric);
                return (
                  <li key={`insight-${idx}`}>
                    <span>{asText(insight.text)}</span>
                    {categories.length > 0 ? (
                      <span className="insight-chip-wrap">
                        {categories.map((category, catIdx) => renderCategoryChip(category, `ins-${idx}-${catIdx}`))}
                      </span>
                    ) : null}
                    {metric ? <strong className="dyn-value"> ({metric})</strong> : null}
                  </li>
                );
              })}
            </ol>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
