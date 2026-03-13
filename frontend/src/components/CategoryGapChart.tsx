import { useMemo, useState } from "react";
import type { GapChartRow } from "../lib/types";

type MetricMode = "pergame" | "zscore";

interface Props {
  rows: GapChartRow[];
  selectedTeam: string | null;
}

function fmtValue(value: number | null | undefined, isPct: boolean): string {
  if (value === null || value === undefined) return "—";
  return isPct ? value.toFixed(4) : value.toFixed(3);
}

function fmtZ(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return (value >= 0 ? "+" : "") + value.toFixed(2);
}

interface BarData {
  display: string;
  category: string;
  myVal: number;
  aboveTeam: string | null;
  aboveVal: number | null;
  belowTeam: string | null;
  belowVal: number | null;
  rangeMin: number;
  rangeMax: number;
  isPct: boolean;
  higherIsBetter: boolean;
}

function buildBarData(rows: GapChartRow[], mode: MetricMode): BarData[] {
  return rows
    .map((r) => {
      if (mode === "zscore") {
        if (r.my_zscore === null || r.z_min === null || r.z_max === null) return null;
        return {
          display: r.display,
          category: r.category,
          myVal: r.my_zscore,
          aboveTeam: r.above_team,
          aboveVal: r.above_zscore,
          belowTeam: r.below_team,
          belowVal: r.below_zscore,
          rangeMin: r.z_min,
          rangeMax: r.z_max,
          isPct: false,
          higherIsBetter: r.higher_is_better,
        };
      }
      return {
        display: r.display,
        category: r.category,
        myVal: r.my_value,
        aboveTeam: r.above_team,
        aboveVal: r.above_value,
        belowTeam: r.below_team,
        belowVal: r.below_value,
        rangeMin: r.league_min,
        rangeMax: r.league_max,
        isPct: r.is_percentage,
        higherIsBetter: r.higher_is_better,
      };
    })
    .filter((d): d is BarData => d !== null);
}

function toPercent(value: number, min: number, max: number): number {
  if (max === min) return 50;
  return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
}

const CAT_CLASS_MAP: Record<string, string> = {
  "FG%": "cat-fg", "FT%": "cat-ft", "3PM/G": "cat-3pm", "3PT%": "cat-3pt",
  "PTS/G": "cat-pts", "REB/G": "cat-reb", "AST/G": "cat-ast",
  "STL/G": "cat-stl", "BLK/G": "cat-blk", "TO/G": "cat-to",
};

function getCatClass(category: string): string {
  if (CAT_CLASS_MAP[category]) return CAT_CLASS_MAP[category];
  const slug = category.toLowerCase().replace(/[^a-z0-9]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  return `cat-${slug}`;
}

function clampLabel(pct: number, halfWidth: number = 5): number {
  return Math.max(halfWidth, Math.min(100 - halfWidth, pct));
}

/** Nudge two label positions apart if they're within `minGap`% of each other. */
function spreadLabels(
  a: number | null,
  b: number | null,
  minGap: number = 12,
): [number | null, number | null] {
  if (a === null || b === null) return [a, b];
  const dist = Math.abs(a - b);
  if (dist >= minGap) return [a, b];
  const mid = (a + b) / 2;
  const half = minGap / 2;
  const lo = Math.max(3, Math.min(97 - minGap, mid - half));
  return a <= b ? [lo, lo + minGap] : [lo + minGap, lo];
}

function truncName(name: string, maxLen: number = 14): string {
  return name.length > maxLen ? name.slice(0, maxLen - 1) + "…" : name;
}

function GapRow({ bar, mode, selectedTeam }: { bar: BarData; mode: MetricMode; selectedTeam: string | null }) {
  const fmt = mode === "zscore"
    ? fmtZ
    : (v: number | null | undefined) => fmtValue(v, bar.isPct);
  const metricLabel = mode === "zscore" ? "Z-Score" : "Per Game Avg";

  const myPct = toPercent(bar.myVal, bar.rangeMin, bar.rangeMax);
  const abovePct = bar.aboveVal !== null ? toPercent(bar.aboveVal, bar.rangeMin, bar.rangeMax) : null;
  const belowPct = bar.belowVal !== null ? toPercent(bar.belowVal, bar.rangeMin, bar.rangeMax) : null;

  let greenLeft: number | null = null;
  let greenWidth: number | null = null;
  let redLeft: number | null = null;
  let redWidth: number | null = null;

  if (belowPct !== null) {
    const left = Math.min(belowPct, myPct);
    const right = Math.max(belowPct, myPct);
    greenLeft = left;
    greenWidth = right - left;
  }

  if (abovePct !== null) {
    const left = Math.min(myPct, abovePct);
    const right = Math.max(myPct, abovePct);
    redLeft = left;
    redWidth = right - left;
  }

  // Tooltip strings
  const myName = selectedTeam ?? "You";
  const myTitle = `${bar.display} — ${myName}: ${fmt(bar.myVal)} (${metricLabel})`;

  const greenGap = bar.belowVal !== null ? Math.abs(bar.myVal - bar.belowVal) : null;
  const greenTitle = bar.belowTeam && greenGap !== null
    ? `Buffer: ${fmt(greenGap)} over ${bar.belowTeam} (${fmt(bar.belowVal)})\nLosing this buffer = −1 roto point`
    : undefined;

  const redGap = bar.aboveVal !== null ? Math.abs(bar.aboveVal - bar.myVal) : null;
  const redTitle = bar.aboveTeam && redGap !== null
    ? `Gap: ${fmt(redGap)} behind ${bar.aboveTeam} (${fmt(bar.aboveVal)})\nClosing this gap = +1 roto point`
    : undefined;

  const belowTitle = bar.belowTeam
    ? `${bar.belowTeam}: ${fmt(bar.belowVal)} (${metricLabel})\nNearest team below you in ${bar.display}`
    : undefined;

  const aboveTitle = bar.aboveTeam
    ? `${bar.aboveTeam}: ${fmt(bar.aboveVal)} (${metricLabel})\nNearest team above you in ${bar.display}`
    : undefined;

  return (
    <div className="gap-row">
      <div className="gap-row-label">
        <span className={`tag ${getCatClass(bar.category)}`}>
          {bar.display.replace("/G", "")}
        </span>
      </div>

      <div className="gap-row-chart">
        {/* Row above the bar: above-team label */}
        <div className="gap-label-row gap-label-row-above">
          {abovePct !== null && bar.aboveTeam && (
            <span
              className="gap-team-label gap-team-label-above"
              style={{ left: `${clampLabel(abovePct)}%` }}
              title={aboveTitle}
            >
              <span className="gap-team-name">{truncName(bar.aboveTeam)}</span>
              <span className="gap-team-val">{fmt(bar.aboveVal)}</span>
            </span>
          )}
        </div>

        {/* The bar track */}
        <div className="gap-bar-track">
          {greenLeft !== null && greenWidth !== null && greenWidth > 0.5 && (
            <div
              className="gap-seg gap-seg-green"
              style={{ left: `${greenLeft}%`, width: `${greenWidth}%` }}
              title={greenTitle}
            />
          )}
          {redLeft !== null && redWidth !== null && redWidth > 0.5 && (
            <div
              className="gap-seg gap-seg-red"
              style={{ left: `${redLeft}%`, width: `${redWidth}%` }}
              title={redTitle}
            />
          )}

          {/* Opponent tick marks */}
          {belowPct !== null && (
            <div
              className="gap-tick gap-tick-green"
              style={{ left: `${belowPct}%` }}
              title={belowTitle}
            />
          )}
          {abovePct !== null && (
            <div
              className="gap-tick gap-tick-red"
              style={{ left: `${abovePct}%` }}
              title={aboveTitle}
            />
          )}

          {/* My marker */}
          <div
            className="gap-my-dot"
            style={{ left: `${myPct}%` }}
            title={myTitle}
          />
        </div>

        {/* Row below the bar: below-team label + my value (spread to avoid overlap) */}
        <div className="gap-label-row gap-label-row-below">
          {(() => {
            const rawBelow = belowPct !== null && bar.belowTeam ? clampLabel(belowPct) : null;
            const rawMy = clampLabel(myPct);
            const [spreadBelow, spreadMy] = spreadLabels(rawBelow, rawMy);
            return (
              <>
                {spreadBelow !== null && bar.belowTeam && (
                  <span
                    className="gap-team-label gap-team-label-below"
                    style={{ left: `${spreadBelow}%` }}
                    title={belowTitle}
                  >
                    <span className="gap-team-name">{truncName(bar.belowTeam)}</span>
                    <span className="gap-team-val">{fmt(bar.belowVal)}</span>
                  </span>
                )}
                <span
                  className="gap-team-label gap-my-label"
                  style={{ left: `${spreadMy ?? rawMy}%` }}
                  title={myTitle}
                >
                  <span className="gap-team-val">{fmt(bar.myVal)}</span>
                </span>
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );
}

export function CategoryGapChart({ rows, selectedTeam }: Props) {
  const [mode, setMode] = useState<MetricMode>("pergame");
  const barData = useMemo(() => buildBarData(rows, mode), [rows, mode]);

  if (rows.length === 0) return null;

  return (
    <section>
      <h2>Category Gap Chart</h2>
      <p className="section-note">
        How close you are to gaining or losing a roto point in each category.
        {selectedTeam ? <> Showing: <strong>{selectedTeam}</strong></> : null}
      </p>

      <div className="gap-controls-row">
        <div className="gap-toggle-row">
          <button
            className={mode === "pergame" ? "gap-toggle gap-toggle-active" : "gap-toggle"}
            onClick={() => setMode("pergame")}
            type="button"
          >
            Per Game Avg
          </button>
          <button
            className={mode === "zscore" ? "gap-toggle gap-toggle-active" : "gap-toggle"}
            onClick={() => setMode("zscore")}
            type="button"
          >
            Z-Score
          </button>
        </div>

        <div className="gap-legend">
          <span className="gap-legend-item">
            <span className="gap-legend-dot gap-legend-dot-my" />
            <span>You</span>
          </span>
          <span className="gap-legend-item">
            <span className="gap-legend-swatch gap-legend-swatch-green" />
            <span>Buffer (safe)</span>
          </span>
          <span className="gap-legend-item">
            <span className="gap-legend-swatch gap-legend-swatch-red" />
            <span>Gap to close</span>
          </span>
          <span className="gap-legend-item">
            <span className="gap-legend-tick gap-legend-tick-red" />
            <span>Team above</span>
          </span>
          <span className="gap-legend-item">
            <span className="gap-legend-tick gap-legend-tick-green" />
            <span>Team below</span>
          </span>
        </div>
      </div>

      <div className="gap-chart-wrap">
        {barData.map((bar) => (
          <GapRow key={bar.category} bar={bar} mode={mode} selectedTeam={selectedTeam} />
        ))}
      </div>
    </section>
  );
}
