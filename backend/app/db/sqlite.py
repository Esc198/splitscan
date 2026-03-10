from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from ..core.config import settings

DB_PATH = settings.database_path


def now_sqlite() -> str:
    """Return the current UTC time using the SQLite DATETIME string format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sqlite_lastrowid(cursor: sqlite3.Cursor) -> int:
    """Extract the last inserted row id or fail with an HTTP 500 error."""
    if cursor.lastrowid is None:
        raise HTTPException(status_code=500, detail="Database insert failed")
    return int(cursor.lastrowid)


def get_conn() -> sqlite3.Connection:
    """Open a SQLite connection configured for row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows_to_dict(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert SQLite row objects into plain dictionaries."""
    return [dict(row) for row in rows]
