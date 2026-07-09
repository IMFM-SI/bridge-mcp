"""Checks for SQL expression and query rendering."""

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, Direction


def test_render_atoms() -> None:
    assert sql.render(sql.IntLit(3)) == "3"
    assert sql.render(sql.BoolLit(True)) == "1"
    assert sql.render(sql.BoolLit(False)) == "0"
    assert sql.render(sql.Null()) == "NULL"
    assert sql.render(sql.StrLit("a'b")) == "'a''b'"
    assert sql.render(sql.Col("g", "n")) == '"g"."n"'


def test_render_compound() -> None:
    expr = sql.BinOp(
        BinaryOp.AND,
        sql.Compare(ComparisonOp.GT, sql.Col("g", "num_vertices"), sql.IntLit(3)),
        sql.Col("g", "is_planar"),
    )
    assert sql.render(expr) == '(("g"."num_vertices" > 3) AND "g"."is_planar")'


def test_render_presence_and_case() -> None:
    assert sql.render(sql.IsNull(sql.Col("g", "d"))) == '("g"."d" IS NULL)'
    assert sql.render(sql.IsNotNull(sql.Col("g", "d"))) == '("g"."d" IS NOT NULL)'
    case = sql.Case(sql.BoolLit(True), sql.IntLit(1), sql.IntLit(2))
    assert sql.render(case) == "(CASE WHEN 1 THEN 1 ELSE 2 END)"


def test_render_json() -> None:
    assert sql.render(sql.JsonArray((sql.IntLit(1), sql.IntLit(2)))) == "json_array(1, 2)"
    assert (
        sql.render(sql.JsonExtract(sql.Col("g", "x"), 0)) == 'json_extract("g"."x", \'$[0]\')'
    )
    assert sql.render(sql.Json(sql.Col("g", "x"))) == 'json("g"."x")'


def test_render_ref() -> None:
    assert sql.render(sql.Ref("m")) == '"m"'


def test_json_array_elides_singleton() -> None:
    assert sql.json_array((sql.IntLit(1),)) == sql.IntLit(1)
    assert sql.json_array((sql.IntLit(1), sql.IntLit(2))) == sql.JsonArray(
        (sql.IntLit(1), sql.IntLit(2))
    )
    assert sql.json_array(()) == sql.JsonArray(())


def test_render_query() -> None:
    q = sql.Query(
        froms=(("graph", "g"),),
        joins=(),
        output=((sql.Col("g", "graph6"), "g6"),),
        cond=sql.BoolLit(True),
        order=((sql.Ref("g6"), Direction.DESC),),
        limit=3,
    )
    assert (
        sql.render_query(q)
        == 'SELECT "g"."graph6" AS "g6" FROM "graph" AS "g" WHERE 1 ORDER BY "g6" DESC LIMIT 3'
    )


def test_render_query_join() -> None:
    q = sql.Query(
        froms=(("maniplex", "m"),),
        joins=(sql.Join("graph", "m_skeleton", (("id", sql.Col("m", "skeleton_id")),)),),
        output=((sql.Col("m_skeleton", "graph6"), "s"),),
        cond=sql.BoolLit(True),
        order=(),
        limit=None,
    )
    assert sql.render_query(q) == (
        'SELECT "m_skeleton"."graph6" AS "s" FROM "maniplex" AS "m"'
        ' LEFT JOIN "graph" AS "m_skeleton" ON "m_skeleton"."id" = "m"."skeleton_id" WHERE 1'
    )
