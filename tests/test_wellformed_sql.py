"""Every rendering the compiler emits parses, checked with EXPLAIN."""

import sqlite3
from collections.abc import Callable
from typing import Any

import pytest

from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.databases import math_data, sym_ob_small
from bridge_mcp.mathql.execute import compiled_sql_query, database_path, safe_alias_predicate

SHAPES: list[dict[str, Any]] = [
    {"domains": [], "output": []},
    {"domains": [], "output": [], "condition": "false"},
    {"domains": [], "output": [["x", "2 + 2"]]},
    {"domains": [], "output": [["x", "(1, 'a')"], ["y", "[1, 2]"], ["z", "(1, 'a').0"]]},
    {"domains": [], "output": [["n", "Graph['Bw'].num_vertices"]]},
    {"domains": [], "output": [["k", "id(Graph['Bw'])"]]},
    {"domains": [["g", "Graph"]], "output": []},
    {
        "domains": [["g", "Graph"]],
        "output": [],
        "order": [["g.num_vertices", "asc"]],
        "limit": 1,
    },
    {
        "domains": [["g", "Graph"]],
        "output": [["n", "g.num_vertices"]],
        "order": [["1", "asc"], ["g.num_edges", "desc"]],
        "limit": 1,
    },
    {"domains": [["g", "Graph"]], "output": [], "order": [["1", "asc"]], "limit": 1},
    {
        "domains": [["g", "Graph"]],
        "output": [["k", "id(g.automorphism_group)"]],
        "order": [["g.automorphism_group.order", "desc"]],
        "limit": 1,
    },
    {"domains": [["g", "Graph"]], "output": [["n", "g.num_vertices"]], "limit": 0},
    {
        "domains": [["g", "Graph"], ["h", "Graph"]],
        "output": [["a", "g.graph6"], ["b", "h.degree_sequence"]],
        "condition": "defined g.diameter && g.degree_sequence == [2, 2, 2]",
        "order": [["a", "desc"], ["g.num_edges", "asc"]],
        "limit": 3,
    },
]


def _explained(
    connection: sqlite3.Connection,
    database: Database,
    is_safe_alias: Callable[[str], bool],
    request: Any,
) -> None:
    rendered = compiled_sql_query(database, is_safe_alias, request)
    connection.execute(f"EXPLAIN {rendered}")


@pytest.fixture
def connection() -> sqlite3.Connection:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


@pytest.fixture
def is_safe_alias(connection: sqlite3.Connection) -> Callable[[str], bool]:
    return safe_alias_predicate(connection, math_data.database)


def test_degenerate_shapes_parse(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    for request in SHAPES:
        _explained(connection, math_data.database, is_safe_alias, request)


def test_every_published_example_parses(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    for example in math_data.database.examples:
        _explained(connection, math_data.database, is_safe_alias, example.query)


def test_every_maniplex_example_parses() -> None:
    path = sym_ob_small.database_path()
    if not path.exists():
        pytest.skip(f"{path} not present")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    is_safe_alias = safe_alias_predicate(connection, sym_ob_small.database)
    for example in sym_ob_small.database.examples:
        _explained(connection, sym_ob_small.database, is_safe_alias, example.query)
    connection.close()
