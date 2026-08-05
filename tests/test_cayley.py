"""Checks for the Cayley graphs, against the bundled database."""

import sqlite3
import subprocess
from collections.abc import Iterator

import networkx
import pytest

from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import database_path
from tests.rows import rows_by_name


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    filled = conn.execute(
        "SELECT count(*) FROM small_group WHERE cayley_graph IS NOT NULL"
    ).fetchone()
    if filled is None or filled[0] == 0:
        conn.close()
        pytest.skip("Cayley graphs not present; run python -m bridge_mcp.generate cayley")
    yield conn
    conn.close()


def test_cayley_graph_of_c6_is_the_hexagon(connection: sqlite3.Connection) -> None:
    canonical = subprocess.run(
        ["labelg"],
        input=networkx.to_graph6_bytes(networkx.cycle_graph(6), header=False).decode(),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Group"]],
            "output": [["graph", "id(g.cayley_graph)"]],
            "condition": "id(g) == (6, 2)",
        },
    )
    assert rows == [{"graph": canonical}]


def test_cayley_graph_of_s4(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Group"]],
            "output": [
                ["vertices", "g.cayley_graph.num_vertices"],
                ["connected", "g.cayley_graph.is_connected"],
                ["regular", "g.cayley_graph.is_regular"],
                ["generators", "g.cayley_generators"],
            ],
            "condition": "id(g) == (24, 12)",
        },
    )
    row = rows[0]
    assert row["vertices"] == 24
    assert row["connected"] is True
    assert row["regular"] is True
    assert len(row["generators"]) == 2  # S4 is 2-generated


def test_cayley_graphs_cover_orders_up_to_100(connection: sqlite3.Connection) -> None:
    missing_small = connection.execute(
        'SELECT count(*) FROM small_group WHERE "order" <= 100 AND cayley_graph IS NULL'
    ).fetchone()[0]
    beyond = connection.execute(
        'SELECT count(*) FROM small_group WHERE "order" > 100 AND cayley_graph IS NOT NULL'
    ).fetchone()[0]
    assert missing_small == 0
    assert beyond == 0


def test_cayley_rows_have_cheap_invariants_only(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [
                ["diameter_defined", "defined g.diameter"],
                ["chromatic_defined", "defined g.chromatic_number"],
            ],
            "condition": ("id(g.source) == 'cayley' && g.is_connected && g.num_vertices > 8"),
            "limit": 5,
        },
    )
    assert rows
    assert all(row["diameter_defined"] for row in rows)
    assert all(not row["chromatic_defined"] for row in rows)


def test_small_cayley_graphs_reuse_geng_rows(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Group"]],
            "output": [["source", "id(g.cayley_graph.source)"]],
            "condition": "g.order <= 8",
        },
    )
    assert rows
    assert all(row["source"] == "geng" for row in rows)
