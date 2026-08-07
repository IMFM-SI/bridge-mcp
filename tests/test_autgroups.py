"""Checks for the graph → automorphism-group link, against the bundled database."""

import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import database_path
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query
from tests.aliases import safe_alias
from tests.rows import rows_by_name


def test_multi_column_join_renders() -> None:
    request: dict[str, Any] = {
        "domains": [["g", "Graph"]],
        "output": [["aut", "g.automorphism_group.structure_description"]],
    }
    rendered = sql.render_query(
        compile_query(
            database, safe_alias(database), check_query(database, from_json(request))
        )
    )
    assert (
        'LEFT JOIN "small_group" AS c3'
        ' ON c3."order" = c1."aut_group_order"'
        ' AND c3."index" = c1."aut_group_index"'
    ) in rendered


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(graph)")}
    if "aut_group_order" not in columns:
        conn.close()
        pytest.skip(
            "automorphism groups not present; run python -m bridge_mcp.generate autgroups"
        )
    yield conn
    conn.close()


def test_triangle_has_automorphism_group_s3(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["aut", "g.automorphism_group.structure_description"]],
            "condition": "g.graph6 == 'Bw'",
        },
    )
    assert rows == [{"aut": "S3"}]


def test_path_graph_has_automorphism_group_c2(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["aut", "g.automorphism_group.structure_description"]],
            "condition": "g.num_vertices == 4 && g.is_tree && g.degree_sequence == [2, 2, 1, 1]",
        },
    )
    assert rows == [{"aut": "C2"}]


def test_complete_graph_k8_exceeds_the_census(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["count", "g.automorphism_count"]],
            "condition": (
                "g.num_vertices == 8 && g.num_edges == 28"
                " && undefined id(g.automorphism_group)"
            ),
        },
    )
    assert rows == [{"count": 40320}]


def test_group_order_agrees_with_the_count(connection: sqlite3.Connection) -> None:
    disagreements = connection.execute(
        "SELECT count(*) FROM graph"
        ' JOIN small_group ON small_group."order" = graph.aut_group_order'
        '  AND small_group."index" = graph.aut_group_index'
        ' WHERE graph.automorphism_count != small_group."order"'
    ).fetchone()[0]
    assert disagreements == 0


def test_graphs_with_nonabelian_automorphism_group(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [
                ["graph6", "g.graph6"],
                ["aut", "g.automorphism_group.structure_description"],
            ],
            "condition": "!g.automorphism_group.is_abelian && g.is_connected",
            "limit": 5,
        },
    )
    assert len(rows) == 5
    assert all(row["aut"] for row in rows)
