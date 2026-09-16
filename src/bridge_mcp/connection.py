"""Read-only SQLite connections, and restricting one to queries."""

from __future__ import annotations

import contextlib
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
    """Open `path` on a connection that cannot write it, hold an attached database,
    or load an extension. `NotSupportedError` from `enable_load_extension` says this
    SQLite was built without extension loading.

    The connection is used from whichever thread the MCP SDK runs a tool on, so
    `check_same_thread` is off; SQLite serializes the access itself, and the read-only
    mode, the attached-database limit and the authorizer belong to the connection."""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
    with contextlib.suppress(sqlite3.NotSupportedError):
        connection.enable_load_extension(False)
    return connection


def restrict_to_queries(connection: sqlite3.Connection) -> None:
    """Admit nothing but a query on `connection` from here on: `INSERT`, `CREATE`,
    `ATTACH`, `PRAGMA` and the rest are refused, `SELECT` and its functions are not."""
    connection.set_authorizer(_authorize)
