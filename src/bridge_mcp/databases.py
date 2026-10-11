"""The databases the server serves, each opened once with its connection."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bridge_mcp.connection import open_read_only, restrict_to_queries
from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.databases import math_data, sym_ob_small
from bridge_mcp.mathql.execute import (
    database_path,
    register_functions,
    safe_alias_predicate,
)


@dataclass(frozen=True)
class Open:
    """A database, its connection, and the alias predicate read from that connection."""

    database: Database
    connection: sqlite3.Connection
    is_safe_alias: Callable[[str], bool]


def _open(database: Database, path: Path) -> Open:
    """Open `path` for `database`, admitting queries alone from the first statement, with
    the database's SQL functions callable."""
    connection = open_read_only(path)
    restrict_to_queries(connection)
    register_functions(connection, database)
    return Open(database, connection, safe_alias_predicate(connection, database))


def _available() -> dict[str, Open]:
    """The databases whose files are present, keyed by name, each with its connection."""
    candidates = (
        ("math_data", math_data.database, database_path()),
        ("sym_ob_small", sym_ob_small.database, sym_ob_small.database_path()),
    )
    return {
        name: _open(database, path) for name, database, path in candidates if path.exists()
    }


DATABASES = _available()


def resolve(name: str | None) -> Open:
    """The database `name` names, or the first one when `name` is `None`."""
    chosen = name if name is not None else next(iter(DATABASES), None)
    if chosen is not None and chosen in DATABASES:
        return DATABASES[chosen]
    else:
        raise ValueError(f"unknown database '{chosen}'; available: {', '.join(DATABASES)}")
