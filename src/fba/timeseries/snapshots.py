"""Save and read stat snapshots for time series analysis."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fba.timeseries.db import get_db, get_default_db_path


def save_snapshot(
    user_id: str,
    league_id: str,
    teams_data: list[dict[str, Any]],
    *,
    db_path: Path | str | None = None,
    snapshot_time: datetime | None = None,
) -> int:
    """Persist a snapshot of all teams' cumulative stats.

    Uses INSERT OR REPLACE so multiple refreshes on the same day keep the latest.

    Returns:
        Number of rows upserted.
    """
    now = snapshot_time or datetime.now(timezone.utc)
    snap_date = now.strftime("%Y-%m-%d")
    snap_at = now.isoformat()

    conn = get_db(db_path)
    try:
        rows = 0
        for team in teams_data:
            stats = team.get("stats", {})
            gp = stats.get("GP", 0)
            if isinstance(gp, str):
                gp = int(gp) if gp else 0
            team_key = team.get("team_key", team.get("team_name", "unknown"))
            team_name = team.get("team_name", "")

            conn.execute(
                """
                INSERT OR REPLACE INTO stat_snapshots
                    (user_id, league_id, snapshot_date, snapshot_at,
                     team_key, team_name, gp, stats_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    league_id,
                    snap_date,
                    snap_at,
                    team_key,
                    team_name,
                    gp,
                    json.dumps(stats),
                ),
            )
            rows += 1
        conn.commit()
        return rows
    finally:
        conn.close()


def get_snapshot_range(
    user_id: str,
    league_id: str,
    *,
    db_path: Path | str | None = None,
) -> tuple[str, str, int] | None:
    """Return (first_date, last_date, total_snapshot_days) or None."""
    conn = get_db(db_path)
    try:
        row = conn.execute(
            """
            SELECT MIN(snapshot_date) AS first_date,
                   MAX(snapshot_date) AS last_date,
                   COUNT(DISTINCT snapshot_date) AS total_days
            FROM stat_snapshots
            WHERE user_id = ? AND league_id = ?
            """,
            (user_id, league_id),
        ).fetchone()
        if row and row["first_date"]:
            return (row["first_date"], row["last_date"], row["total_days"])
        return None
    finally:
        conn.close()


def get_snapshots_for_date(
    user_id: str,
    league_id: str,
    target_date: str,
    *,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return all team snapshots for a specific date.

    Each dict has: team_key, team_name, gp, stats (parsed JSON).
    """
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """
            SELECT team_key, team_name, gp, stats_json
            FROM stat_snapshots
            WHERE user_id = ? AND league_id = ? AND snapshot_date = ?
            ORDER BY team_name
            """,
            (user_id, league_id, target_date),
        ).fetchall()
        return [
            {
                "team_key": r["team_key"],
                "team_name": r["team_name"],
                "gp": r["gp"],
                "stats": json.loads(r["stats_json"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_closest_snapshot_date(
    user_id: str,
    league_id: str,
    target_date: str,
    *,
    direction: str = "before",
    db_path: Path | str | None = None,
) -> str | None:
    """Find the closest snapshot date on or before/after the target date."""
    conn = get_db(db_path)
    try:
        if direction == "before":
            row = conn.execute(
                """
                SELECT MAX(snapshot_date) AS d
                FROM stat_snapshots
                WHERE user_id = ? AND league_id = ? AND snapshot_date <= ?
                """,
                (user_id, league_id, target_date),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT MIN(snapshot_date) AS d
                FROM stat_snapshots
                WHERE user_id = ? AND league_id = ? AND snapshot_date >= ?
                """,
                (user_id, league_id, target_date),
            ).fetchone()
        return row["d"] if row and row["d"] else None
    finally:
        conn.close()


def get_all_snapshot_dates(
    user_id: str,
    league_id: str,
    *,
    db_path: Path | str | None = None,
) -> list[str]:
    """Return all distinct snapshot dates in ascending order."""
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT snapshot_date
            FROM stat_snapshots
            WHERE user_id = ? AND league_id = ?
            ORDER BY snapshot_date
            """,
            (user_id, league_id),
        ).fetchall()
        return [r["snapshot_date"] for r in rows]
    finally:
        conn.close()
