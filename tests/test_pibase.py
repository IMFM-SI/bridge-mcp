"""Checks for the π-Base domains of math_data: SQL rendering (offline), and
execution against the bundled database once its pibase_* tables are generated."""

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


def test_composite_key_id() -> None:
    rendered = _rendered({"domains": [["t", "Trait"]], "output": [["key", "id(t)"]]})
    assert rendered == (
        'SELECT json_array("t"."space", "t"."property") AS "key"'
        ' FROM "pibase_trait" AS "t" WHERE 1'
    )


def test_composite_key_object() -> None:
    rendered = _rendered(
        {
            "domains": [["s", "Space"]],
            "output": [["v", "Trait['S000026', 'P000016'].value"]],
        }
    )
    assert (
        'LEFT JOIN "pibase_trait" AS "Trait"'
        ' ON "Trait"."space" = \'S000026\' AND "Trait"."property" = \'P000016\''
    ) in rendered


def test_id_tuple_comparison_canonicalized() -> None:
    rendered = _rendered(
        {
            "domains": [["t", "Trait"]],
            "output": [["v", "t.value"]],
            "condition": "id(t) == ('S000149', 'P000053')",
        }
    )
    assert (
        'json(json_array("t"."space", "t"."property"))'
        " = json(json_array('S000149', 'P000053'))"
    ) in rendered


def test_foreign_keys_join() -> None:
    rendered = _rendered(
        {
            "domains": [["t", "Trait"]],
            "output": [["space", "t.space.name"], ["property", "t.property.name"]],
            "condition": "t.value",
        }
    )
    assert (
        'LEFT JOIN "pibase_space" AS "t_space" ON "t_space"."uid" = "t"."space"'
    ) in rendered
    assert (
        'LEFT JOIN "pibase_property" AS "t_property" ON "t_property"."uid" = "t"."property"'
    ) in rendered


def test_nullable_theorem_link() -> None:
    rendered = _rendered(
        {
            "domains": [["t", "Trait"]],
            "output": [["statement", "t.theorem.statement"]],
            "condition": "defined id(t.theorem)",
        }
    )
    assert 'WHERE ("t_theorem"."uid" IS NOT NULL)' in rendered


def test_describe_includes_pibase_domains() -> None:
    described: Any = database.describe()
    domains = {d["name"]: d for d in described["domains"]}
    assert {"Graph", "Space", "Property", "Trait", "Theorem"} <= set(domains)
    links = {f["label"]: f["domain"] for f in domains["Trait"]["domainFields"]}
    assert links == {"space": "Space", "property": "Property", "theorem": "Theorem"}
    trait_fields = {f["label"]: f["type"] for f in domains["Trait"]["inputFields"]}
    assert trait_fields["premises"] == "list prod [string, bool]"


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    generated = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'pibase_space'"
    ).fetchone()
    if generated is None:
        conn.close()
        pytest.skip("pibase tables not present; run python -m bridge_mcp.generate pibase")
    yield conn
    conn.close()


def test_discrete_two_point_is_compact_and_metrizable(
    connection: sqlite3.Connection,
) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["t", "Trait"]],
            "output": [["prop", "t.property.name"], ["value", "t.value"]],
            "condition": (
                "id(t.space) == 'S000001'"
                " && (id(t.property) == 'P000016' || id(t.property) == 'P000053')"
            ),
            "order": [["prop", "asc"]],
        },
    )
    assert [(row["prop"], row["value"]) for row in rows] == [
        ("Compact", True),
        ("Metrizable", True),
    ]


def test_provenance_of_a_trait(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["t", "Trait"]],
            "output": [
                ["value", "t.value"],
                ["asserted", "t.asserted"],
                ["theorem", "t.theorem.statement"],
                ["premises", "t.premises"],
            ],
            "condition": "id(t) == ('S000149', 'P000053')",
        },
    )
    row = rows[0]  # the two-sided long line is not metrizable
    assert row["value"] is False
    assert (row["theorem"] is None) == bool(row["asserted"])
    assert (row["premises"] == []) == bool(row["asserted"])


def test_compact_nonmetrizable_spaces_exist(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["t1", "Trait"], ["t2", "Trait"]],
            "output": [["space", "t1.space.name"]],
            "condition": (
                "id(t1.property) == 'P000016' && t1.value"
                " && id(t2.property) == 'P000053' && !t2.value"
                " && id(t1.space) == id(t2.space)"
            ),
            "limit": 5,
        },
    )
    assert len(rows) == 5
    assert all(row["space"] for row in rows)


def test_table_sizes(connection: sqlite3.Connection) -> None:
    spaces = connection.execute("SELECT count(*) FROM pibase_space").fetchone()[0]
    traits = connection.execute("SELECT count(*) FROM pibase_trait").fetchone()[0]
    derived = connection.execute(
        "SELECT count(*) FROM pibase_trait WHERE asserted = 0"
    ).fetchone()[0]
    assert spaces >= 200
    assert traits >= 40000
    assert 0 < derived < traits
