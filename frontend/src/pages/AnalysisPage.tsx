import type { ReactNode } from "react";
import { ChangeEvent, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getAnalysis } from "../lib/api";
import { formatFixed, toNumber } from "../lib/format";
import { useAsyncData } from "../lib/useAsyncData";

const CAT_CLASS_MAP: Record<string, string> = {
  "FG%": "cat-fg",
  "FT%": "cat-ft",
  "3PM/G": "cat-3pm",
  "PTS/G": "cat-pts",
  "REB/G": "cat-reb",
  "AST/G": "cat-ast",
  "STL/G": "cat-stl",
  "BLK/G": "cat-blk"
};

function renderTagPill(tag: unknown): ReactNode {
  if (tag !== "TARGET" && tag !== "DEFEND") {
    return "—";
  }
  return <span className={`tag ${tag === "TARGET" ? "tag-target" : "tag-defend"}`}>{tag}</span>;
}

function normalizeCategory(value: unknown): string | null {
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object" && "display" in value) {
    const display = (value as { display?: unknown }).display;
    if (typeof display === "string") {
      return display;
    }
  }
  return null;
}

function renderCategoryList(value: unknown) {
  if (!Array.isArray(value) || value.length === 0) {
    return "—";
  }

  const categories = value
    .map(normalizeCategory)
    .filter((item): item is string => Boolean(item));

  if (categories.length === 0) {
    return "—";
  }

  return (
    <div className="tag-list">
      {categories.map((category) => (
        <span key={category} className={`tag ${CAT_CLASS_MAP[category] ?? ""}`}>
          {category.replace("/G", "")}
        </span>
      ))}
    </div>
  );
}

function renderTeamWithRank(value: unknown, teamPgRank: Record<string, string>): ReactNode {
  if (typeof value !== "string" || value.length === 0) {
    return "—";
  }

  const rank = teamPgRank[value];
  return (
    <>
      {value}
      {rank ? <span className="ref-rank"> ({rank})</span> : null}
    </>
  );
}

function analysisColumns(teamPgRank: Record<string, string>) {
  return [
    {
      key: "display",
      label: "Category",
      align: "left" as const,
      headerClassName: "col-cat",
      cellClassName: "col-cat"
    },
    { key: "value", label: "Value", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
    { key: "rank", label: "Rank", align: "right" as const },
    {
      key: "next_better_team",
      label: "Better Team",
      align: "left" as const,
      headerClassName: "col-ref",
      cellClassName: "col-ref",
      render: (value: unknown) => renderTeamWithRank(value, teamPgRank)
    },
    { key: "next_better_value", label: "Value", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
    { key: "gap_up", label: "Gap+", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
    { key: "z_gap_up", label: "z+", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
    {
      key: "next_worse_team",
      label: "Worse Team",
      align: "left" as const,
      headerClassName: "col-ref",
      cellClassName: "col-ref",
      render: (value: unknown) => renderTeamWithRank(value, teamPgRank)
    },
    { key: "next_worse_value", label: "Value", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
    { key: "gap_down", label: "Gap−", align: "right" as const, render: (value: unknown) => formatFixed(value, 3) },
    { key: "z_gap_down", label: "z−", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
    { key: "target_score", label: "Score", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
    { key: "tag", label: "Tag", align: "center" as const, cellClassName: "col-tag", render: renderTagPill }
  ];
}

const LEAGUE_COLUMNS = [
  { key: "team_name", label: "Team", align: "left" as const },
  { key: "pg_rank", label: "PG Rank", align: "right" as const },
  {
    key: "rank_total",
    label: "PG Total",
    align: "right" as const,
    render: (value: unknown) => {
      const num = toNumber(value);
      return num === null ? "—" : String(num);
    }
  },
  {
    key: "total_points",
    label: "Roto Total",
    align: "right" as const,
    render: (value: unknown) => {
      const num = toNumber(value);
      return num === null ? "—" : num.toLocaleString("en-US", { maximumFractionDigits: 1 });
    }
  },
  { key: "targets", label: "L1 Targets", align: "left" as const, render: renderCategoryList },
  { key: "defends", label: "L1 Defends", align: "left" as const, render: renderCategoryList },
  { key: "cluster_targets", label: "Cluster Targets", align: "left" as const, render: renderCategoryList },
  { key: "cluster_defends", label: "Cluster Defends", align: "left" as const, render: renderCategoryList }
];

function formatSigma(value: unknown, category: unknown) {
  const num = toNumber(value);
  if (num === null) return "—";
  return category === "FG%" || category === "FT%" ? num.toFixed(4) : num.toFixed(3);
}

function formatPlain(value: unknown) {
  const num = toNumber(value);
  return num === null ? "—" : String(num);
}

const CLUSTER_COLUMNS = [
  { key: "display", label: "Category", align: "left" as const },
  { key: "rank", label: "Rank", align: "right" as const },
  { key: "sigma", label: "σ", align: "right" as const, render: (value: unknown, row: Record<string, unknown>) => formatSigma(value, row.category) },
  { key: "z_to_gain_1", label: "z+1", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "z_to_gain_2", label: "z+2", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "z_to_gain_3", label: "z+3", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "points_up_within_T", label: "Pts Up ≤ 0.75σ", align: "right" as const, render: formatPlain },
  { key: "cluster_up_score", label: "Up Score", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "z_to_lose_1", label: "z−1", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "z_to_lose_2", label: "z−2", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "z_to_lose_3", label: "z−3", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "points_down_within_T", label: "Pts Down ≤ 0.75σ", align: "right" as const, render: formatPlain },
  { key: "cluster_down_risk", label: "Dn Risk", align: "right" as const, render: (value: unknown) => formatFixed(value, 2) },
  { key: "tag", label: "Tag", align: "center" as const, render: renderTagPill }
];

export function AnalysisPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTeam = searchParams.get("team")?.trim() || undefined;
  const loader = useCallback((signal: AbortSignal) => getAnalysis(requestedTeam, signal), [requestedTeam]);
  const { data, loading, error, reload } = useAsyncData(loader, [requestedTeam]);

  const hasData = Boolean(data?.has_data);
  const leagueId = data?.league_id ?? "";

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

  const analysisRows = data?.analysis ?? [];
  const targetRows = analysisRows.filter((row) => row.tag === "TARGET");
  const defendRows = analysisRows.filter((row) => row.tag === "DEFEND");
  const teamPgRank = data?.team_pg_rank ?? {};
  const leagueRows = data?.league_summary ?? [];
  const clusterRows = analysisRows.map((row) => {
    const item = row as Record<string, unknown>;
    const categoryKey = typeof item.category === "string" ? item.category : "";
    const teamCluster = (data?.team_cluster ?? {}) as Record<string, Record<string, unknown>>;
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
  const clusterTargetRows = clusterRows.filter((row) => row.tag === "TARGET");
  const clusterDefendRows = clusterRows.filter((row) => row.tag === "DEFEND");

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
          {analysisRows.length > 0 ? (
            <section className="summary-panel">
              <div className="summary-group summary-target">
                <h3>Categories to Target</h3>
                <div className="summary-items">
                  {targetRows.map((row) => (
                    <span key={`target-${row.category}`} className="summary-item">
                      <strong>{row.display.replace("/G", "")}</strong>
                      {row.z_gap_up !== null ? (
                        <span className="summary-val">({formatFixed(row.z_gap_up, 2)}σ)</span>
                      ) : null}
                    </span>
                  ))}
                </div>
                {clusterTargetRows.length > 0 ? (
                  <>
                    <div className="summary-sub-label">Cluster</div>
                    <div className="summary-items">
                      {clusterTargetRows.map((row) => (
                        <span key={`cluster-target-${String(row.category)}`} className="summary-item">
                          <strong>{String(row.display).replace("/G", "")}</strong>
                          {row.cluster_up_score !== null && row.cluster_up_score !== undefined ? (
                            <span className="summary-val">({formatFixed(row.cluster_up_score, 2)})</span>
                          ) : null}
                        </span>
                      ))}
                    </div>
                  </>
                ) : null}
              </div>
              <div className="summary-group summary-defend">
                <h3>Categories to Defend</h3>
                <div className="summary-items">
                  {defendRows.map((row) => (
                    <span key={`defend-${row.category}`} className="summary-item">
                      <strong>{row.display.replace("/G", "")}</strong>
                      {row.z_gap_down !== null ? (
                        <span className="summary-val">({formatFixed(row.z_gap_down, 2)}σ)</span>
                      ) : null}
                    </span>
                  ))}
                </div>
                {clusterDefendRows.length > 0 ? (
                  <>
                    <div className="summary-sub-label">Cluster</div>
                    <div className="summary-items">
                      {clusterDefendRows.map((row) => (
                        <span key={`cluster-defend-${String(row.category)}`} className="summary-item">
                          <strong>{String(row.display).replace("/G", "")}</strong>
                          {row.cluster_down_risk !== null && row.cluster_down_risk !== undefined ? (
                            <span className="summary-val">({formatFixed(row.cluster_down_risk, 2)})</span>
                          ) : null}
                        </span>
                      ))}
                    </div>
                  </>
                ) : null}
              </div>
            </section>
          ) : null}

          <section>
            <h2>Category Analysis - {data.selected_team}</h2>
            <div className="control-row">
              <label htmlFor="team-select">Analyze team</label>
              <select id="team-select" onChange={onTeamChange} value={data.selected_team ?? ""}>
                {data.team_names.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
            <DataTable
              columns={analysisColumns(teamPgRank)}
              initialSort={{ key: "target_score", desc: true }}
              rowClassName={(row) => {
                const tag = row.tag;
                if (tag === "TARGET") return "row-target";
                if (tag === "DEFEND") return "row-defend";
                return undefined;
              }}
              rows={analysisRows}
              tableClassName="analysis-table"
            />
          </section>

          <details className="analysis-key">
            <summary className="analysis-key-title">How to read this</summary>
            <ul className="analysis-key-list">
              <li>
                <strong>z+ (Effort):</strong> Standard deviations you must improve to pass the next team — lower is easier
                to close.
              </li>
              <li>
                <strong>z− (Risk):</strong> Standard deviations separating you from the team behind — lower means
                you&apos;re more vulnerable.
              </li>
              <li>
                <strong>Score:</strong> Higher = better ROI. Prioritizes easy gains, lightly weights downside protection.
              </li>
            </ul>
            <div className="analysis-key-rules">
              <span>
                <strong>Rule of thumb —</strong> z+ &lt; 0.40: great target · 0.40-0.75: possible · &gt; 0.75: usually not
                worth chasing
              </span>
              <span>
                <strong>Risk —</strong> z− &lt; 0.30: defend this category
              </span>
            </div>
            <p className="analysis-key-example">
              Example: STL with z+ = 0.18 is a high-leverage target — a small improvement can gain a roto point.
            </p>
          </details>

          {analysisRows.length > 0 && Object.keys(data.team_cluster ?? {}).length > 0 ? (
            <section>
              <h2>Cluster Leverage (Multi-Point Potential)</h2>
              <p className="section-note">
                This measures how many roto points you can gain (or lose) if teams are tightly clustered. It looks beyond
                the next opponent.
              </p>
              <DataTable
                columns={CLUSTER_COLUMNS}
                initialSort={{ key: "cluster_up_score", desc: true }}
                rowClassName={(row) => {
                  const tag = row.tag;
                  if (tag === "TARGET") return "row-target";
                  if (tag === "DEFEND") return "row-defend";
                  return undefined;
                }}
                rows={clusterRows}
                tableClassName="analysis-table cluster-table"
              />
              <details className="cluster-legend">
                <summary className="analysis-key-title">How to read this</summary>
                <ul className="analysis-key-list">
                  <li>
                    <strong>σ (Sigma):</strong> Population std dev for this category — the natural unit of spread across all
                    teams.
                  </li>
                  <li>
                    <strong>z+1 / z+2 / z+3:</strong> Standardized improvement (in σ units) needed to jump 1, 2, or 3 roto
                    points upward. Smaller = more reachable. &quot;—&quot; means you&apos;re already at or beyond that tier.
                  </li>
                  <li>
                    <strong>z−1 / z−2 / z−3:</strong> Standardized decline (in σ units) needed to drop 1, 2, or 3 roto points
                    downward. Smaller = more fragile. &quot;—&quot; means you&apos;re already at the bottom tier.
                  </li>
                  <li>
                    <strong>Pts Up:</strong> How many roto-point jumps sit within a 0.75σ effort window above you — teams
                    bunched close enough that one push gains multiple spots.
                  </li>
                  <li>
                    <strong>Up Score:</strong> Pts Up ÷ 0.75 — a density-adjusted ROI. Higher = more multi-point leverage per
                    unit of effort.
                  </li>
                  <li>
                    <strong>Pts Dn:</strong> How many roto-point drops sit within 0.75σ below you — teams so close that a
                    small slip costs multiple positions.
                  </li>
                  <li>
                    <strong>Dn Risk:</strong> Pts Dn ÷ 0.75 — a density-adjusted fragility score. Higher = more exposure to a
                    multi-point collapse.
                  </li>
                </ul>
                <div className="analysis-key-rules">
                  <span>
                    <strong>High Cluster Up Score</strong> = can gain multiple points with modest improvement — prioritize this
                    category.
                  </span>
                  <span>
                    <strong>High Cluster Down Risk</strong> = could lose multiple points if you slip — defend this category.
                  </span>
                </div>
              </details>
            </section>
          ) : null}

          <section>
            <h2>League Overview</h2>
            <p className="section-note">
              All teams ranked by per-game total (highest = best). Layer 1 and Cluster target/defend categories are sorted
              from highest to lowest priority score.
            </p>
            <DataTable columns={LEAGUE_COLUMNS} initialSort={{ key: "rank_total", desc: true }} rows={leagueRows} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
