"""Checks for SQL expression and query rendering."""

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, Direction, UnaryOp


def test_render_atoms() -> None:
    assert sql.render(sql.IntLit(3)) == "3"
    assert sql.render(sql.BoolLit(True)) == "1"
    assert sql.render(sql.BoolLit(False)) == "0"
    assert sql.render(sql.Null()) == "NULL"
    assert sql.render(sql.StrLit("a'b")) == "'a''b'"
    assert sql.render(sql.Col("c1", "n")) == 'c1."n"'


def test_render_compound() -> None:
    expr = sql.BinOp(
        BinaryOp.AND,
        sql.Compare(ComparisonOp.GT, sql.Col("c1", "num_vertices"), sql.IntLit(3)),
        sql.Col("c1", "is_planar"),
    )
    assert sql.render(expr) == '((c1."num_vertices" > 3) AND c1."is_planar")'


def test_render_presence_and_case() -> None:
    assert sql.render(sql.IsNull(sql.Col("c1", "d"))) == '(c1."d" IS NULL)'
    assert sql.render(sql.IsNotNull(sql.Col("c1", "d"))) == '(c1."d" IS NOT NULL)'
    case = sql.Case(sql.BoolLit(True), sql.IntLit(1), sql.IntLit(2))
    assert sql.render(case) == "(CASE WHEN 1 THEN 1 ELSE 2 END)"


def test_render_json() -> None:
    assert sql.render(sql.JsonArray((sql.IntLit(1), sql.IntLit(2)))) == "json_array(1, 2)"
    assert (
        sql.render(sql.JsonExtract(sql.Col("c1", "x"), 0)) == "json_extract(c1.\"x\", '$[0]')"
    )
    assert sql.render(sql.Json(sql.Col("c1", "x"))) == 'json(c1."x")'


def test_render_ref() -> None:
    assert sql.render(sql.Ref("c2")) == "c2"


def test_json_array_elides_singleton() -> None:
    assert sql.json_array((sql.IntLit(1),)) == sql.IntLit(1)
    assert sql.json_array((sql.IntLit(1), sql.IntLit(2))) == sql.JsonArray(
        (sql.IntLit(1), sql.IntLit(2))
    )
    assert sql.json_array(()) == sql.JsonArray(())


def test_is_constant_literals() -> None:
    assert sql.is_constant(sql.IntLit(1))
    assert sql.is_constant(sql.StrLit("abc"))
    assert sql.is_constant(sql.BoolLit(True))
    assert sql.is_constant(sql.Null())


def test_is_constant_column_reference_and_call() -> None:
    assert not sql.is_constant(sql.Col("c1", "n"))
    assert not sql.is_constant(sql.Ref("c2"))
    assert not sql.is_constant(sql.Call("abs", (sql.IntLit(-1),)))


def test_is_constant_follows_the_parts() -> None:
    column = sql.Col("c1", "n")
    assert sql.is_constant(sql.UnOp(UnaryOp.NOT, sql.BoolLit(True)))
    assert not sql.is_constant(sql.UnOp(UnaryOp.NOT, column))
    assert sql.is_constant(sql.BinOp(BinaryOp.ADD, sql.IntLit(1), sql.IntLit(0)))
    assert not sql.is_constant(sql.BinOp(BinaryOp.ADD, sql.IntLit(1), column))
    assert sql.is_constant(sql.Case(sql.BoolLit(True), sql.IntLit(1), sql.IntLit(2)))
    assert not sql.is_constant(sql.Case(sql.BoolLit(True), sql.IntLit(1), column))
    assert sql.is_constant(sql.JsonArray((sql.IntLit(1), sql.IntLit(2))))
    assert not sql.is_constant(sql.JsonArray((sql.IntLit(1), column)))


def test_render_query() -> None:
    q = sql.Query(
        froms=(("graph", "c1"),),
        joins=(),
        output=((sql.Col("c1", "graph6"), "c2"),),
        cond=sql.BoolLit(True),
        order=((sql.Ref("c2"), Direction.DESC),),
        limit=3,
    )
    assert (
        sql.render_query(q)
        == 'SELECT c1."graph6" AS c2 FROM "graph" AS c1 WHERE 1 ORDER BY c2 DESC LIMIT 3'
    )


def test_render_query_join() -> None:
    q = sql.Query(
        froms=(("maniplex", "c1"),),
        joins=(sql.Join("graph", "c3", (("id", sql.Col("c1", "skeleton_id")),)),),
        output=((sql.Col("c3", "graph6"), "c2"),),
        cond=sql.BoolLit(True),
        order=(),
        limit=None,
    )
    assert sql.render_query(q) == (
        'SELECT c3."graph6" AS c2 FROM "maniplex" AS c1'
        ' LEFT JOIN "graph" AS c3 ON c3."id" = c1."skeleton_id" WHERE 1'
    )
