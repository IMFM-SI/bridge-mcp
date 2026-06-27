"""Checks for SQL expression rendering."""

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp


def test_render_atoms() -> None:
    assert sql.render(sql.IntLit(3)) == "3"
    assert sql.render(sql.BoolLit(True)) == "1"
    assert sql.render(sql.BoolLit(False)) == "0"
    assert sql.render(sql.Null()) == "NULL"
    assert sql.render(sql.StrLit("a'b")) == "'a''b'"
    assert sql.render(sql.Col("g", "n")) == "g.n"


def test_render_compound() -> None:
    expr = sql.BinOp(
        BinaryOp.AND,
        sql.Compare(ComparisonOp.GT, sql.Col("g", "num_vertices"), sql.IntLit(3)),
        sql.Col("g", "is_planar"),
    )
    assert sql.render(expr) == "((g.num_vertices > 3) AND g.is_planar)"


def test_render_presence_and_case() -> None:
    assert sql.render(sql.IsNull(sql.Col("g", "d"))) == "(g.d IS NULL)"
    assert sql.render(sql.IsNotNull(sql.Col("g", "d"))) == "(g.d IS NOT NULL)"
    case = sql.Case(sql.BoolLit(True), sql.IntLit(1), sql.IntLit(2))
    assert sql.render(case) == "(CASE WHEN 1 THEN 1 ELSE 2 END)"


def test_render_json() -> None:
    assert sql.render(sql.JsonArray((sql.IntLit(1), sql.IntLit(2)))) == "json_array(1, 2)"
    assert sql.render(sql.JsonExtract(sql.Col("g", "x"), 0)) == "json_extract(g.x, '$[0]')"
