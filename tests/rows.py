"""A query helper for the suites that check database content."""

import sqlite3
from collections.abc import Mapping
from typing import Any

from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.execute import run_query, safe_alias_predicate


def rows_by_name(
    connection: sqlite3.Connection, database: Database, request: Mapping[str, Any]
) -> list[dict[str, object]]:
    """Run a query and key each row by its column names, which are distinct."""
    predicate = safe_alias_predicate(connection, database)
    return [dict(row) for row in run_query(connection, database, predicate, request)]
