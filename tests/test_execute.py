"""End-to-end checks against the bundled database, skipped when it is absent."""

import sqlite3
from collections.abc import Iterator

import pytest

from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import database_path, run_query

DB = database_path()


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    if not DB.exists():
        pytest.skip(f"{DB} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(DB)
    yield conn
    conn.close()


def test_triangle(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": {"graph6": "g.graph6", "num_edges": "g.num_edges"},
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows == [{"graph6": "Bw", "num_edges": 3}]


def test_trees_on_five(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": {"graph6": "g.graph6"},
            "condition": "g.num_vertices == 5 && g.is_tree",
        },
    )
    assert len(rows) == 3


def test_degree_sequence_equality(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": {"graph6": "g.graph6", "degrees": "g.degree_sequence"},
            "condition": "g.degree_sequence == [2, 2, 2]",
        },
    )
    assert rows == [{"graph6": "Bw", "degrees": [2, 2, 2]}]


def test_id_output(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": {"gid": "id(g)"},
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows == [{"gid": "Bw"}]


def test_null_becomes_none(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": {"diameter": "g.diameter"},
            "condition": "!g.is_connected && g.num_vertices == 2",
        },
    )
    assert rows == [{"diameter": None}]


def test_order_by_alias(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": {"g6": "id(g)", "spread": "g.max_degree - g.min_degree"},
            "condition": "g.num_vertices == 5",
            "order": [["spread", "desc"]],
            "limit": 3,
        },
    )
    assert [row["spread"] for row in rows] == [3, 3, 3]
