"""SQLite schema and helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_daily_share (
    code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    total_share REAL NOT NULL,
    name TEXT,
    PRIMARY KEY (code, trade_date)
);

CREATE TABLE IF NOT EXISTS index_daily (
    code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume REAL,
    PRIMARY KEY (code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_share_date ON etf_daily_share(trade_date);
CREATE INDEX IF NOT EXISTS idx_index_date ON index_daily(trade_date);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_shares(
    conn: sqlite3.Connection,
    rows: Iterable[tuple[str, str, float, str | None]],
) -> int:
    """rows: (code, trade_date, total_share, name). total_share in 万份."""
    cur = conn.executemany(
        """
        INSERT INTO etf_daily_share (code, trade_date, total_share, name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code, trade_date) DO UPDATE SET
            total_share = excluded.total_share,
            name = COALESCE(excluded.name, etf_daily_share.name)
        """,
        list(rows),
    )
    conn.commit()
    return cur.rowcount


def upsert_index(
    conn: sqlite3.Connection,
    rows: Iterable[tuple[str, str, float, float, float, float, float | None]],
) -> int:
    """rows: (code, trade_date, open, high, low, close, volume)."""
    cur = conn.executemany(
        """
        INSERT INTO index_daily (code, trade_date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, trade_date) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume
        """,
        list(rows),
    )
    conn.commit()
    return cur.rowcount
