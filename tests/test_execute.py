"""End-to-end checks against the bundled database, skipped when it is absent."""

import sqlite3
from collections.abc import Iterator

import pytest

from bridge_mcp.mathql.databases.small_graphs import database
from bridge_mcp.mathql.execute import database_path, run_query

DB = database_path()


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    if not DB.exists():
        pytest.skip(f"{DB} not present; run scripts/generate_graphs.py")
    conn = sqlite3.connect(DB)
    yield conn
    conn.close()


def test_triangle(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": ["g.graph6", "g.num_edges"],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows == [{"g.graph6": "Bw", "g.num_edges": 3}]


def test_trees_on_five(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": ["g.graph6"],
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
            "output": ["g.graph6"],
            "condition": "g.degree_sequence == [2, 2, 2]",
        },
    )
    assert rows == [{"g.graph6": "Bw"}]


def test_whole_object(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": ["g"],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows[0]["g"]["degree_sequence"] == [2, 2, 2]
    assert rows[0]["g"]["is_connected"] is True
    assert rows[0]["g"]["diameter"] == 1
