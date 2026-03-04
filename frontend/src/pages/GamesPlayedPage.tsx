import { FormEvent, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { DataTable } from "../components/DataTable";
import { StatusPanel } from "../components/StatusPanel";
import { getGamesPlayed } from "../lib/api";
import { formatFixed, toNumber } from "../lib/format";
import { useAsyncData } from "../lib/useAsyncData";

const GAMES_COLUMNS = [
  { key: "team_name", label: "Team", align: "left" as const },
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
                {data.start_str} - {data.end_str}, inclusive)
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
        </>
      ) : null}
    </AppShell>
  );
}
