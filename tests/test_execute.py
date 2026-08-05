"""End-to-end checks against the bundled database, skipped when it is absent."""

import dataclasses
import sqlite3
from collections.abc import Iterator

import pytest

from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import database_path, run_query
from tests.toy import DATABASE as TOY

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
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"], ["num_edges", "g.num_edges"]],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows == [[("graph6", "Bw"), ("num_edges", 3)]]


def test_trees_on_five(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"]],
            "condition": "g.num_vertices == 5 && g.is_tree",
        },
    )
    assert len(rows) == 3


def test_degree_sequence_equality(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"], ["degrees", "g.degree_sequence"]],
            "condition": "g.degree_sequence == [2, 2, 2]",
        },
    )
    assert rows == [[("graph6", "Bw"), ("degrees", [2, 2, 2])]]


def test_id_output(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["gid", "id(g)"]],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows == [[("gid", "Bw")]]


def test_null_becomes_none(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["diameter", "g.diameter"]],
            "condition": "!g.is_connected && g.num_vertices == 2",
        },
    )
    assert rows == [[("diameter", None)]]


def test_order_by_alias(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["g6", "id(g)"], ["spread", "g.max_degree - g.min_degree"]],
            "condition": "g.num_vertices == 5",
            "order": [["spread", "desc"]],
            "limit": 3,
        },
    )
    assert [dict(row)["spread"] for row in rows] == [3, 3, 3]


def test_a_row_is_pairs_in_output_order(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [[name, "g.num_edges"] for name in ("zeta", "alpha", "mu", "beta")],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert [name for name, _ in rows[0]] == ["zeta", "alpha", "mu", "beta"]


def test_a_repeated_output_name_is_rejected(connection: sqlite3.Connection) -> None:
    with pytest.raises(MathQLError):
        run_query(
            connection,
            database,
            {
                "domains": [["g", "Graph"]],
                "output": [["n", "g.num_vertices"], ["n", "g.num_edges"]],
            },
        )


def test_postprocess_appends_its_columns(connection: sqlite3.Connection) -> None:
    with_plus = dataclasses.replace(database, post_functions=TOY.post_functions)
    rows = run_query(
        connection,
        with_plus,
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "g.num_vertices"]],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
            "postprocess": [["k", "plus(n, 1)"], ["m", "k * 2"]],
        },
    )
    assert rows == [[("n", 3), ("k", 4), ("m", 8)]]


def test_the_two_stages_agree_on_the_same_row(connection: sqlite3.Connection) -> None:
    """`defined` and a list comparison answer alike in a condition and in postprocess."""
    request = {
        "domains": [["g", "Graph"]],
        "output": [
            ["d", "g.diameter"],
            ["ds", "g.degree_sequence"],
            ["in_sql_defined", "defined g.diameter"],
            ["in_sql_equal", "g.degree_sequence == [2, 2, 2]"],
        ],
        "condition": "g.num_vertices <= 3",
        "postprocess": [
            ["in_post_defined", "defined d"],
            ["in_post_equal", "ds == [2, 2, 2]"],
        ],
    }
    rows = [dict(row) for row in run_query(connection, database, request)]
    assert rows
    assert all(row["in_sql_defined"] == row["in_post_defined"] for row in rows)
    assert all(row["in_sql_equal"] == row["in_post_equal"] for row in rows)
    assert {row["in_post_defined"] for row in rows} == {True, False}  # both cases occur
