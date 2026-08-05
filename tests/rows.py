"""A query helper for the suites that check database content."""

import sqlite3
from collections.abc import Mapping
from typing import Any

from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.execute import run_query


def rows_by_name(
    connection: sqlite3.Connection, database: Database, request: Mapping[str, Any]
) -> list[dict[str, object]]:
    """Run a query and key each row by its column names. A repeated output column name
    keeps its last value, so a suite that asks for one queries `run_query` directly."""
    return [dict(row) for row in run_query(connection, database, request)]
