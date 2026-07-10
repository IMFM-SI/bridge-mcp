"""Checks for the π-Base domains of math_data: SQL rendering (offline), and
execution against the bundled database once its pibase_* tables are generated."""

from typing import Any

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query


def _rendered(request: dict[str, Any]) -> str:
    return sql.render_query(
        compile_query(database, check_query(database.context(), from_json(request)))
    )


def test_composite_key_id() -> None:
    rendered = _rendered({"domains": [["t", "Trait"]], "output": {"key": "id(t)"}})
    assert rendered == (
        'SELECT json_array("t"."space", "t"."property") AS "key"'
        ' FROM "pibase_trait" AS "t" WHERE 1'
    )


def test_composite_key_object() -> None:
    rendered = _rendered(
        {
            "domains": [["s", "Space"]],
            "output": {"v": "Trait['S000026', 'P000016'].value"},
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
            "output": {"v": "t.value"},
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
            "output": {"space": "t.space.name", "property": "t.property.name"},
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
            "output": {"statement": "t.theorem.statement"},
            "condition": "defined id(t.theorem)",
        }
    )
    assert 'WHERE ("t_theorem"."uid" IS NOT NULL)' in rendered


def test_describe_includes_pibase_domains() -> None:
    described: Any = database.describe()
    domains = {d["name"]: d for d in described["domains"]}
    assert {"Graph8", "Space", "Property", "Trait", "Theorem"} <= set(domains)
    links = {f["label"]: f["domain"] for f in domains["Trait"]["domainFields"]}
    assert links == {"space": "Space", "property": "Property", "theorem": "Theorem"}
    trait_fields = {f["label"]: f["type"] for f in domains["Trait"]["inputFields"]}
    assert trait_fields["premises"] == "list prod [string, bool]"
