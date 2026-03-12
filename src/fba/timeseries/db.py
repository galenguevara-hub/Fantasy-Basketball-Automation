"""SQLite database lifecycle for time series snapshots."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stat_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    league_id TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    team_key TEXT NOT NULL,
    team_name TEXT NOT NULL,
    gp INTEGER NOT NULL,
    stats_json TEXT NOT NULL,
    UNIQUE(user_id, league_id, snapshot_date, team_key)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
    ON stat_snapshots(user_id, league_id, snapshot_date);

CREATE INDEX IF NOT EXISTS idx_snapshots_team
    ON stat_snapshots(user_id, league_id, team_key, snapshot_date);
"""


def get_default_db_path() -> Path:
    """Return the default database file path (``data/timeseries.db``)."""
    return _DEFAULT_DB_DIR / "timeseries.db"


def get_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection.  Caller is responsible for closing it."""
    path = str(db_path or get_default_db_path())
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Create tables and indexes if they do not already exist."""
    path = db_path or get_default_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_db(path)
    try:
        conn.executescript(_SCHEMA_SQL)
    finally:
        conn.close()
