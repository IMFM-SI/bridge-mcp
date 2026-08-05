"""Execute a type-checked query against a SQLite connection, producing JSON rows."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import Any, assert_never

from bridge_mcp.mathql import query, sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query
from bridge_mcp.mathql.types import (
    BoolType,
    IntType,
    ListType,
    ProductType,
    StringType,
    Ty,
)


def database_path() -> Path:
    """The bundled `math_data` database, or the path in `BRIDGE_MCP_DB` if set."""
    override = os.environ.get("BRIDGE_MCP_DB")
    if override is not None:
        return Path(override)
    else:
        return Path(
            str(resources.files("bridge_mcp.mathql.databases").joinpath("math-data.db"))
        )


def _decode_cell(ty: Ty, cell: Any) -> object:
    """Decode one output cell at its declared type; a NULL cell is None. Lists and
    products are stored as JSON text and returned decoded."""
    if cell is None:
        return None
    else:
        match ty:
            case IntType():
                return int(cell)
            case BoolType():
                return bool(cell)
            case StringType():
                return str(cell)
            case ListType() | ProductType():
                try:
                    return json.loads(cell)
                except json.JSONDecodeError as error:
                    raise MathQLError(
                        f"expected JSON in a list or product column: {error}"
                    ) from error
        assert_never(ty)


def _decode_row(q: query.Query, row: Sequence[Any]) -> list[tuple[str, object]]:
    """One row's output cells, each paired with its column name, in output order."""
    return [
        (column.name, _decode_cell(column.ty, cell))
        for column, cell in zip(q.output, row, strict=True)
    ]


def run(
    connection: sqlite3.Connection, database: Database, q: query.Query
) -> list[list[tuple[str, object]]]:
    """Run a type-checked query, returning each row as its list of name/value pairs."""
    rendered = sql.render_query(compile_query(database, q))
    return [_decode_row(q, row) for row in connection.execute(rendered).fetchall()]


def run_query(
    connection: sqlite3.Connection, database: Database, request: Mapping[str, Any]
) -> list[list[tuple[str, object]]]:
    """Parse, type-check, compile, and run a query from its JSON form."""
    return run(connection, database, check_query(database, from_json(request)))
