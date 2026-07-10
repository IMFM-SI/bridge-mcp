"""Checks for the sym_ob_small database: offline SQL rendering, and execution when
the database file is present (see the README)."""

import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.databases.sym_ob_small import database, database_path
from bridge_mcp.mathql.execute import run_query
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query


def _rendered(request: dict[str, Any]) -> str:
    return sql.render_query(
        compile_query(database, check_query(database.context(), from_json(request)))
    )


def test_two_hop_chain_shares_joins() -> None:
    rendered = _rendered(
        {
            "domains": [["m", "Maniplex"]],
            "output": {"s6": "m.skeleton.graph.sparse6"},
            "condition": "m.skeleton.graph.num_vertices > 4",
        }
    )
    assert rendered.count("LEFT JOIN") == 2
    assert (
        'LEFT JOIN "canonicallabeling" AS "m_skeleton"'
        ' ON "m_skeleton"."id" = "m"."cl_one_skeleton_id"'
    ) in rendered
    assert (
        'LEFT JOIN "graph" AS "m_skeleton_graph"'
        ' ON "m_skeleton_graph"."id" = "m_skeleton"."graph_in_sparse6_id"'
    ) in rendered
    assert '("m_skeleton_graph"."order" > 4)' in rendered


def test_keyword_column_quoted() -> None:
    rendered = _rendered({"domains": [["g", "Graph"]], "output": {"n": "g.num_vertices"}})
    assert '"g"."order" AS "n"' in rendered


def test_tuple_comparison_canonicalized() -> None:
    rendered = _rendered(
        {
            "domains": [["m", "Maniplex"]],
            "output": {"id": "id(m)"},
            "condition": "m.schlafli_symbol == (4, 8, 8)",
        }
    )
    assert '(json("m"."schlafli_symbol") = json(json_array(4, 8, 8)))' in rendered


def test_describe_lists_domain_fields() -> None:
    described: Any = database.describe()
    domains = {d["name"]: d for d in described["domains"]}
    links = {f["label"]: f["domain"] for f in domains["Maniplex"]["domainFields"]}
    assert links == {
        "flag_graph": "CanonicalLabeling",
        "skeleton": "CanonicalLabeling",
        "coskeleton": "CanonicalLabeling",
    }
    assert {f["label"] for f in domains["CanonicalLabeling"]["domainFields"]} == {
        "graph",
        "parameters",
    }


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    yield conn
    conn.close()


def test_smallest_polytopal_skeleton(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["m", "Maniplex"]],
            "output": {
                "id": "id(m)",
                "flags": "m.num_flags",
                "s6": "m.skeleton.graph.sparse6",
            },
            "condition": "m.polytopality == 'Polytopal'",
            "order": [["flags", "asc"]],
            "limit": 1,
        },
    )
    assert rows == [{"id": 98692, "flags": 16, "s6": ":An"}]


def test_schlafli_tuple_roundtrip(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["m", "Maniplex"]],
            "output": {"symbol": "m.schlafli_symbol"},
            "condition": "m.orientable && m.schlafli_symbol == (4, 8, 8)",
            "limit": 1,
        },
    )
    assert rows == [{"symbol": [4, 8, 8]}]


def test_house_of_graphs_references(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        {
            "domains": [["r", "GraphExternalReference"]],
            "output": {"source": "r.source", "vertices": "r.graph.num_vertices"},
            "condition": "r.source == 'HoG'",
            "limit": 2,
        },
    )
    assert all(row["source"] == "HoG" and row["vertices"] > 0 for row in rows)
