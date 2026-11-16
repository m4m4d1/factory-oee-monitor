"""SQLite storage for production records and downtime events (standard library only)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

PRODUCTION_COLUMNS = ["line_id", "timestamp", "planned_minutes", "run_minutes", "total_count", "good_count"]
DOWNTIME_COLUMNS = ["line_id", "start", "minutes", "reason"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS production (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    planned_minutes REAL, run_minutes REAL, total_count INTEGER, good_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_production_line_time ON production (line_id, timestamp);
CREATE TABLE IF NOT EXISTS downtime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id TEXT NOT NULL,
    start TEXT NOT NULL,
    minutes REAL NOT NULL,
    reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_downtime_line_start ON downtime (line_id, start);
"""


def db_path() -> Path:
    return config.DB_PATH


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def to_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def _insert(table: str, columns: list[str], rows: list[dict], time_column: str) -> int:
    data = [tuple(to_iso(r[c]) if c == time_column else r[c] for c in columns) for r in rows]
    with connect() as conn:
        conn.executemany(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})", data)
    return len(data)


def insert_production(rows: list[dict]) -> int:
    return _insert("production", PRODUCTION_COLUMNS, rows, "timestamp")


def insert_downtime(rows: list[dict]) -> int:
    return _insert("downtime", DOWNTIME_COLUMNS, rows, "start")


def count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM production").fetchone()[0]


def count_downtime() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM downtime").fetchone()[0]


def latest_timestamp() -> str | None:
    with connect() as conn:
        return conn.execute("SELECT MAX(timestamp) FROM production").fetchone()[0]


def latest_by_line() -> dict[str, dict]:
    sql = """
        SELECT p.* FROM production p
        JOIN (SELECT line_id, MAX(timestamp) AS ts FROM production GROUP BY line_id) m
          ON p.line_id = m.line_id AND p.timestamp = m.ts
    """
    with connect() as conn:
        return {row["line_id"]: dict(row) for row in conn.execute(sql)}


def production(line_id: str | None = None, hours: int = 72) -> list[dict]:
    """Production records of the last `hours`, oldest first."""
    since = to_iso(datetime.now(timezone.utc) - timedelta(hours=hours))
    sql = "SELECT * FROM production WHERE timestamp >= ?"
    args: list = [since]
    if line_id:
        sql += " AND line_id = ?"
        args.append(line_id)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY timestamp, line_id", args)]


def downtime(line_id: str | None = None, hours: int = 24) -> list[dict]:
    """Downtime events that started in the last `hours`, oldest first."""
    since = to_iso(datetime.now(timezone.utc) - timedelta(hours=hours))
    sql = "SELECT * FROM downtime WHERE start >= ?"
    args: list = [since]
    if line_id:
        sql += " AND line_id = ?"
        args.append(line_id)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY start, line_id", args)]
