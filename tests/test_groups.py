"""Checks for the Group domain: SQL rendering, and execution against the bundled
database once the small_group table is generated."""

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
from tests.rows import rows_by_name


def _rendered(request: dict[str, Any]) -> str:
    return sql.render_query(compile_query(database, check_query(database, from_json(request))))


def test_composite_key_object() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Group"]],
            "output": [["name", "Group[24, 12].structure_description"]],
        }
    )
    assert (
        'LEFT JOIN "small_group" AS "Group" ON "Group"."order" = 24 AND "Group"."index" = 12'
    ) in rendered


def test_keyword_columns_are_quoted() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Group"]],
            "output": [["n", "g.order"]],
            "order": [["g.order", "desc"]],
        }
    )
    assert '"g"."order" AS "n"' in rendered
    assert 'ORDER BY "g"."order" DESC' in rendered


def test_describe_includes_group_domain() -> None:
    described: Any = database.describe()
    domains = {d["name"]: d for d in described["domains"]}
    fields = {f["label"]: f["type"] for f in domains["Group"]["inputFields"]}
    assert fields["abelianization"] == "list int"
    assert fields["cayley_generators"] == "list string"
    links = {f["label"]: f["domain"] for f in domains["Group"]["domainFields"]}
    assert links == {"cayley_graph": "Graph"}


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    generated = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'small_group'"
    ).fetchone()
    if generated is None:
        conn.close()
        pytest.skip("small_group table not present; run python -m bridge_mcp.generate groups")
    yield conn
    conn.close()


def test_alternating_group_a5(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Group"]],
            "output": [
                ["name", "g.structure_description"],
                ["simple", "g.is_simple"],
                ["solvable", "g.is_solvable"],
                ["classes", "g.num_conjugacy_classes"],
            ],
            "condition": "id(g) == (60, 5)",
        },
    )
    assert rows == [{"name": "A5", "simple": True, "solvable": False, "classes": 5}]


def test_smallest_nonsolvable_group_is_a5(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Group"]],
            "output": [["id", "id(g)"], ["name", "g.structure_description"]],
            "condition": "!g.is_solvable",
            "order": [["g.order", "asc"]],
            "limit": 1,
        },
    )
    assert rows == [{"id": [60, 5], "name": "A5"}]


def test_nilpotency_class_is_undefined_for_s3(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Group"]],
            "output": [["nc", "g.nilpotency_class"], ["dl", "g.derived_length"]],
            "condition": "id(g) == (6, 1) && undefined g.nilpotency_class",
        },
    )
    assert rows == [{"nc": None, "dl": 2}]


def test_census_counts(connection: sqlite3.Connection) -> None:
    total = connection.execute("SELECT count(*) FROM small_group").fetchone()[0]
    of_64 = connection.execute(
        'SELECT count(*) FROM small_group WHERE "order" = 64'
    ).fetchone()[0]
    assert total == 1268
    assert of_64 == 267


def test_abelian_invariants(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Group"]],
            "output": [["name", "g.structure_description"]],
            "condition": "g.order == 4 && g.abelianization == [2, 2]",
        },
    )
    assert rows == [{"name": "C2 x C2"}]
