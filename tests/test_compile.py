"""Checks for compiling type-checked queries to SQL, over a toy database with a
foreign key."""

import pytest

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.database import Column, Database, ForeignKey, Schema
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.query import Query
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query
from bridge_mcp.mathql.types import BoolType, IntType, StringType

GRAPH = Schema(
    table="graph",
    columns={
        "graph6": Column("graph6", StringType(), True, ""),
        "n": Column("n", IntType(), False, ""),
        "planar": Column("planar", BoolType(), False, ""),
    },
    foreign_keys={},
    doc="",
)
MANIPLEX = Schema(
    table="maniplex",
    columns={
        "mid": Column("mid", IntType(), True, ""),
        "size": Column("size", IntType(), False, ""),
    },
    foreign_keys={"skeleton": ForeignKey("Graph", (("skeleton_graph6", "graph6"),), "")},
    doc="",
)
TOY = Database(
    overview="toy",
    constants=(),
    domains={"Graph": GRAPH, "Maniplex": MANIPLEX},
    examples=(),
)


def _typed(request: dict[str, object]) -> Query:
    return check_query(TOY.context(), from_json(request))


def _rendered(request: dict[str, object]) -> str:
    return sql.render_query(compile_query(TOY, _typed(request)))


def test_fields_and_condition() -> None:
    assert (
        _rendered(
            {"domains": [["g", "Graph"]], "output": [["n", "g.n"]], "condition": "g.n > 3"}
        )
        == 'SELECT "g"."n" AS "n" FROM "graph" AS "g" WHERE ("g"."n" > 3)'
    )


def test_id_of_single_column_key() -> None:
    assert _rendered({"domains": [["g", "Graph"]], "output": [["gid", "id(g)"]]}) == (
        'SELECT "g"."graph6" AS "gid" FROM "graph" AS "g" WHERE 1'
    )


def test_domain_field_hoists_one_join() -> None:
    rendered = _rendered(
        {
            "domains": [["m", "Maniplex"]],
            "output": [["s", "m.skeleton.graph6"]],
            "condition": "m.skeleton.n > 3",
        }
    )
    assert rendered == (
        'SELECT "m_skeleton"."graph6" AS "s" FROM "maniplex" AS "m"'
        ' LEFT JOIN "graph" AS "m_skeleton" ON "m_skeleton"."graph6" = "m"."skeleton_graph6"'
        ' WHERE ("m_skeleton"."n" > 3)'
    )


def test_obj_hoists_a_join() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "Graph['abc'].n"]],
            "condition": "g.n == Graph['abc'].n",
        }
    )
    assert rendered == (
        'SELECT "Graph"."n" AS "n" FROM "graph" AS "g"'
        ' LEFT JOIN "graph" AS "Graph" ON "Graph"."graph6" = \'abc\''
        ' WHERE ("g"."n" = "Graph"."n")'
    )


def test_defined_on_domain_field() -> None:
    rendered = _rendered(
        {
            "domains": [["m", "Maniplex"]],
            "output": [["mid", "m.mid"]],
            "condition": "defined id(m.skeleton)",
        }
    )
    assert 'WHERE ("m_skeleton"."graph6" IS NOT NULL)' in rendered


def test_order_by_alias_renders_bare() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["m", "g.n * g.n"]],
            "order": [["m", "desc"]],
            "limit": 3,
        }
    )
    assert rendered == (
        'SELECT ("g"."n" * "g"."n") AS "m" FROM "graph" AS "g" WHERE 1 ORDER BY "m" DESC LIMIT 3'
    )


def test_fresh_alias_avoids_variables() -> None:
    rendered = _rendered(
        {
            "domains": [["graph", "Graph"]],
            "output": [["n", "Graph['abc'].n"]],
        }
    )
    assert 'LEFT JOIN "graph" AS "Graph2" ON "Graph2"."graph6" = \'abc\'' in rendered


def test_tuples_projections_and_conditional() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["pair", "(g.n, g.planar)"], ["first", "(g.n, g.planar).0"]],
            "condition": "if g.planar then g.n > 0 else [1, 2] == [g.n, g.n]",
        }
    )
    assert 'json_array("g"."n", "g"."planar") AS "pair"' in rendered
    assert 'json_extract(json_array("g"."n", "g"."planar"), \'$[0]\') AS "first"' in rendered
    assert (
        'CASE WHEN "g"."planar" THEN ("g"."n" > 0)'
        ' ELSE (json(json_array(1, 2)) = json(json_array("g"."n", "g"."n"))) END' in rendered
    )


def test_condition_does_not_see_aliases() -> None:
    with pytest.raises(MathQLError):
        _typed({"domains": [["g", "Graph"]], "output": [["m", "g.n"]], "condition": "m > 0"})
