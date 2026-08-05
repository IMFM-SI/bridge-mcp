"""Every query the compiler emits parses: each rendering goes through SQLite's EXPLAIN,
which parses and plans it without running it."""

import sqlite3
from typing import Any

import pytest

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.databases import math_data, sym_ob_small
from bridge_mcp.mathql.execute import database_path
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query

SHAPES: list[dict[str, Any]] = [
    {"domains": [], "output": []},
    {"domains": [], "output": [], "condition": "false"},
    {"domains": [], "output": [["x", "2 + 2"]]},
    {"domains": [], "output": [["x", "(1, 'a')"], ["y", "[1, 2]"], ["z", "(1, 'a').0"]]},
    {"domains": [], "output": [["n", "Graph['Bw'].num_vertices"]]},
    {"domains": [], "output": [["k", "id(Graph['Bw'])"]]},
    {"domains": [["g", "Graph"]], "output": []},
    {"domains": [["g", "Graph"]], "output": [], "order": [["1", "asc"]], "limit": 1},
    {"domains": [["g", "Graph"]], "output": [["n", "g.num_vertices"]], "limit": 0},
    {
        "domains": [["g", "Graph"], ["h", "Graph"]],
        "output": [["a", "g.graph6"], ["b", "h.degree_sequence"]],
        "condition": "defined g.diameter && g.degree_sequence == [2, 2, 2]",
        "order": [["a", "desc"], ["g.num_edges", "asc"]],
        "limit": 3,
    },
]


def _explained(connection: sqlite3.Connection, database: Database, request: Any) -> None:
    rendered = sql.render_query(
        compile_query(database, check_query(database, from_json(request)))
    )
    connection.execute(f"EXPLAIN {rendered}")


@pytest.fixture
def connection() -> sqlite3.Connection:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def test_degenerate_shapes_parse(connection: sqlite3.Connection) -> None:
    for request in SHAPES:
        _explained(connection, math_data.database, request)


def test_every_published_example_parses(connection: sqlite3.Connection) -> None:
    for example in math_data.database.examples:
        _explained(connection, math_data.database, example.query)


def test_every_maniplex_example_parses() -> None:
    path = sym_ob_small.database_path()
    if not path.exists():
        pytest.skip(f"{path} not present")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    for example in sym_ob_small.database.examples:
        _explained(connection, sym_ob_small.database, example.query)
    connection.close()
