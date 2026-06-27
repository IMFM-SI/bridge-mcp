"""Execute a typed query against a SQLite connection, producing JSON rows."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from bridge_mcp.mathql import query
from bridge_mcp.mathql.compile import SqlContext, compile_expr
from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.sql import render, render_direction
from bridge_mcp.mathql.typecheck import check_query


def _sql_context(database: Database, variables: tuple[query.Binding, ...]) -> SqlContext:
    columns = {
        (binding.var, field.label): field.column
        for binding in variables
        for field in database.domains[binding.domain].fields
    }
    return SqlContext(columns=columns, constants=database.sql_constants())


def render_query(database: Database, q: query.Query) -> str:
    """Render a type-checked query to a single SQLite SELECT statement."""
    ctx = _sql_context(database, q.variables)
    froms = ", ".join(f"{database.domains[b.domain].table} AS {b.var}" for b in q.variables)
    columns = ", ".join(
        f"{b.var}.{field.column}"
        for b in q.variables
        for field in database.domains[b.domain].fields
    )
    where = render(compile_expr(ctx, q.condition))
    order = (
        " ORDER BY "
        + ", ".join(
            f"{render(compile_expr(ctx, e.key))} {render_direction(e.direction)}"
            for e in q.order
        )
        if q.order
        else ""
    )
    limit = f" LIMIT {q.limit}" if q.limit is not None else ""
    return f"SELECT {columns} FROM {froms} WHERE {where}{order}{limit}"


def _decode_row(
    database: Database, q: query.Query, cells: Sequence[Any]
) -> dict[str, dict[str, object]]:
    decoded: dict[str, dict[str, object]] = {}
    offset = 0
    for binding in q.variables:
        domain = database.domains[binding.domain]
        width = len(domain.fields)
        decoded[binding.var] = domain.decode(cells[offset : offset + width])
        offset += width
    return decoded


def _output_entry(
    decoded: Mapping[str, dict[str, object]], item: query.OutputItem
) -> tuple[str, object]:
    if item.label is None:
        return item.var, decoded[item.var]
    else:
        return f"{item.var}.{item.label}", decoded[item.var][item.label]


def run(
    connection: sqlite3.Connection, database: Database, q: query.Query
) -> list[dict[str, object]]:
    """Run a type-checked query, returning one JSON object per matching row."""
    cursor = connection.execute(render_query(database, q))
    return [
        dict(_output_entry(_decode_row(database, q, row), item) for item in q.output)
        for row in cursor.fetchall()
    ]


def run_query(
    connection: sqlite3.Connection, database: Database, request: Mapping[str, Any]
) -> list[dict[str, object]]:
    """Parse, type-check, compile, and run a query from its JSON form."""
    typed = check_query(database.typing_context(), from_json(request))
    return run(connection, database, typed)
