"""The sql component: the `sql` tool, running one SELECT against a database."""

from __future__ import annotations

import sqlite3
from typing import Any

from mcp.server.mcpserver import MCPServer

from bridge_mcp.databases import resolve
from bridge_mcp.failure import anticipating

INSTRUCTIONS = """## Running SQL directly
`sql` runs one SELECT statement against a database and returns the rows. The connection is
read-only and admits a query alone, so the database and every other file stay as they are.

Examples:
- `sql("SELECT name, sql FROM sqlite_master WHERE type = 'table'")` returns each table
  with its CREATE TABLE text, which is where the schema comes from.
- `sql("SELECT graph6, num_edges FROM graph WHERE num_vertices = 5 ORDER BY num_edges")`
  returns rows of the graph table."""


def _cell(value: Any) -> Any:
    """A cell as JSON carries it: a blob as its hexadecimal text, anything else as
    it stands."""
    return value.hex() if isinstance(value, bytes) else value


def register(mcp: MCPServer) -> None:
    """Register the `sql` tool on `mcp`."""

    @mcp.tool()
    @anticipating(sqlite3.Error, ValueError)
    def sql(statement: str, database: str | None = None) -> list[list[tuple[str, Any]]]:
        """Run one SQL SELECT statement and return the rows, each a list of
        [column name, value] pairs, the names taken from the statement's result columns.

        The statement is a single SELECT, and may use joins, subqueries, aggregates,
        common table expressions and SQLite's built-in functions. The connection is
        read-only and admits a query alone, so every other statement — INSERT, UPDATE,
        DELETE, CREATE, DROP, ALTER, ATTACH, PRAGMA, CREATE TEMP TABLE — ends in
        "not authorized", leaving the database and every other file as they were.

        The schema comes from `sqlite_master`, whose `sql` column holds each table's
        CREATE TABLE text and which lists the views and indexes under `type`:
            SELECT name, sql FROM sqlite_master WHERE type = 'table'

        statement: the SELECT to run.
        database: which database to query (optional; the default is the first).
        """
        cursor = resolve(database).connection.execute(statement)
        names = [description[0] for description in cursor.description or []]
        return [list(zip(names, map(_cell, row), strict=True)) for row in cursor.fetchall()]
