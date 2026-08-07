"""The sql component: the `sql` tool, running one SELECT against a database."""

from __future__ import annotations

import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.databases import DATABASES, Open

DEFAULT_LIMIT = 200

INSTRUCTIONS = f"""## Running SQL directly
`sql` runs one SELECT statement against a database and returns the rows. The connection is
read-only and admits nothing but a query, so INSERT, UPDATE, DELETE, CREATE, DROP, ALTER,
ATTACH and PRAGMA are all refused, and a statement can reach no file besides the database.
For the tables and their columns, run
`SELECT name, sql FROM sqlite_master WHERE type = 'table'`.
It returns at most {DEFAULT_LIMIT} rows unless `limit` says otherwise."""


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
    def sql(
        statement: str, database: str | None = None, limit: int = DEFAULT_LIMIT
    ) -> list[list[tuple[str, Any]]]:
        """Run one SQL SELECT statement and return the rows, each a list of
        [column name, value] pairs.

        What is allowed: a single SELECT, with joins, subqueries, aggregates, common table
        expressions and SQLite's built-in functions. What is refused: everything else.
        The connection is read-only, so the database cannot be changed, and it admits only
        queries, so INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, ATTACH, PRAGMA and
        CREATE TEMP TABLE all fail with "not authorized". One statement runs per call.

        To see the tables and their columns, run
            SELECT name, sql FROM sqlite_master WHERE type = 'table'
        whose `sql` column holds each table's full CREATE TABLE text; the same table lists
        the views and indexes. `PRAGMA table_info` and `pragma_table_info()` are refused,
        so `sqlite_master` is the way to read the schema.

        statement: the SELECT to run.
        database: which database to query (optional; the default is the first).
        limit: how many rows to return at most.
        """
        connection = resolve(database).connection
        try:
            cursor = connection.execute(statement)
            names = [description[0] for description in cursor.description or []]
            return [list(zip(names, row, strict=True)) for row in cursor.fetchmany(limit)]
        except sqlite3.Error as error:
            raise ValueError(str(error)) from error
