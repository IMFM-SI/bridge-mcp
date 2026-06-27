"""Checks for compiling typed expressions to SQL."""

from bridge_mcp.mathql import expr, sql
from bridge_mcp.mathql.compile import SqlContext, compile_expr
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp
from bridge_mcp.mathql.types import IntType

CTX = SqlContext(
    columns={("g", "num_vertices"): "num_vertices", ("g", "is_planar"): "is_planar"},
    constants={},
)


def _sql(e: expr.Expr) -> str:
    return sql.render(compile_expr(CTX, e))


def test_field_and_compare() -> None:
    e = expr.Compare(
        ComparisonOp.GT, IntType(), expr.Field("g", "num_vertices"), expr.IntLit(3)
    )
    assert _sql(e) == "(g.num_vertices > 3)"


def test_binop() -> None:
    e = expr.BinOp(
        BinaryOp.AND,
        expr.Compare(
            ComparisonOp.GT, IntType(), expr.Field("g", "num_vertices"), expr.IntLit(3)
        ),
        expr.Field("g", "is_planar"),
    )
    assert _sql(e) == "((g.num_vertices > 3) AND g.is_planar)"


def test_tuple_and_projection() -> None:
    pair = expr.TupleExpr((expr.Field("g", "num_vertices"), expr.Field("g", "is_planar")))
    assert _sql(pair) == "json_array(g.num_vertices, g.is_planar)"
    assert (
        _sql(expr.Proj(pair, 0))
        == "json_extract(json_array(g.num_vertices, g.is_planar), '$[0]')"
    )


def test_list() -> None:
    assert _sql(expr.ListExpr((expr.IntLit(1), expr.IntLit(2)))) == "json_array(1, 2)"


def test_presence_and_conditional() -> None:
    assert (
        _sql(expr.Defined(expr.Field("g", "num_vertices"))) == "(g.num_vertices IS NOT NULL)"
    )
    e = expr.Ite(expr.Field("g", "is_planar"), expr.IntLit(1), expr.IntLit(2))
    assert _sql(e) == "(CASE WHEN g.is_planar THEN 1 ELSE 2 END)"
