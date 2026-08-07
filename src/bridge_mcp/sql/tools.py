"""The sql component: the `sql` tool, running one SELECT against a database."""

from __future__ import annotations

import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.databases import DATABASES, Open

INSTRUCTIONS = """## Running SQL directly
`sql` runs one SELECT statement against a database and returns the rows. The connection is
read-only and admits a query alone, so the database and every other file stay as they are.

Examples:
- `sql("SELECT name, sql FROM sqlite_master WHERE type = 'table'")` returns each table
  with its CREATE TABLE text, which is where the schema comes from.
- `sql("SELECT graph6, num_edges FROM graph WHERE num_vertices = 5 ORDER BY num_edges")`
  returns rows of the graph table."""


def register(mcp: FastMCP) -> None:
    """Register the `sql` tool on `mcp`."""

    default = next(iter(DATABASES), None)

    def resolve(database: str | None) -> Open:
        name = database if database is not None else default
        if name is not None and name in DATABASES:
            return DATABASES[name]
        else:
            raise ValueError(f"unknown database '{name}'; available: {', '.join(DATABASES)}")

    @mcp.tool()
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
        connection = resolve(database).connection
        try:
            cursor = connection.execute(statement)
            names = [description[0] for description in cursor.description or []]
            return [list(zip(names, row, strict=True)) for row in cursor.fetchall()]
        except sqlite3.Error as error:
            raise ValueError(str(error)) from error
