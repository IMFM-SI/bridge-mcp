"""Read-only SQLite connections, and restricting one to queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_ALLOWED = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }
)


def _authorize(
    action: int,
    first: str | None,
    second: str | None,
    database: str | None,
    trigger: str | None,
) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY


def open_read_only(path: Path) -> sqlite3.Connection:
    """Open `path` so that SQLite refuses every write to it."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def restrict_to_queries(connection: sqlite3.Connection) -> None:
    """Admit nothing but a query on `connection` from here on: `INSERT`, `CREATE`,
    `ATTACH`, `PRAGMA` and the rest are refused, `SELECT` and its functions are not."""
    connection.set_authorizer(_authorize)
