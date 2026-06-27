"""Checks for the expression parser. Spans are excluded from equality."""

import pytest

from bridge_mcp.mathql import input as ast
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, UnaryOp
from bridge_mcp.mathql.parser import parse_expression as p


def test_atoms() -> None:
    assert p("42") == ast.IntLit(42)
    assert p("true") == ast.BoolLit(True)
    assert p("false") == ast.BoolLit(False)
    assert p('"hi"') == ast.StrLit("hi")
    assert p("x") == ast.Const("x")
    assert p("trueish") == ast.Const("trueish")
    assert p("g.n") == ast.Field("g", "n")


def test_precedence() -> None:
    assert p("g.planar && g.n > 0") == ast.BinOp(
        BinaryOp.AND,
        ast.Field("g", "planar"),
        ast.Compare(ComparisonOp.GT, ast.Field("g", "n"), ast.IntLit(0)),
    )
    assert p("-3 + 4 * 2") == ast.BinOp(
        BinaryOp.ADD,
        ast.UnOp(UnaryOp.NEG, ast.IntLit(3)),
        ast.BinOp(BinaryOp.MUL, ast.IntLit(4), ast.IntLit(2)),
    )


def test_left_associativity() -> None:
    assert p("1 - 2 - 3") == ast.BinOp(
        BinaryOp.SUB, ast.BinOp(BinaryOp.SUB, ast.IntLit(1), ast.IntLit(2)), ast.IntLit(3)
    )


def test_lists_tuples_projection() -> None:
    assert p("[]") == ast.ListExpr(())
    assert p("[1, 2]") == ast.ListExpr((ast.IntLit(1), ast.IntLit(2)))
    assert p("(g.n)") == ast.Field("g", "n")  # grouping, not a tuple
    assert p("(g.n, g.planar)") == ast.TupleExpr(
        (ast.Field("g", "n"), ast.Field("g", "planar"))
    )
    assert p("(g.n, g.planar).0") == ast.Proj(
        ast.TupleExpr((ast.Field("g", "n"), ast.Field("g", "planar"))), 0
    )


def test_conditional_and_presence() -> None:
    assert p("if g.planar then 1 else 2") == ast.Ite(
        ast.Field("g", "planar"), ast.IntLit(1), ast.IntLit(2)
    )
    assert p("defined g.n") == ast.Defined(ast.Field("g", "n"))
    assert p("!g.planar") == ast.UnOp(UnaryOp.NOT, ast.Field("g", "planar"))


def test_utf8_operators() -> None:
    assert p("g.n ≤ 3") == ast.Compare(ComparisonOp.LE, ast.Field("g", "n"), ast.IntLit(3))
    assert p("a ∧ b") == ast.BinOp(BinaryOp.AND, ast.Const("a"), ast.Const("b"))


def test_span_is_recorded_but_ignored_in_equality() -> None:
    parsed = p("42")
    assert parsed.span is not None
    assert parsed == ast.IntLit(42)  # span defaults to None on the right; still equal


def test_string_escapes() -> None:
    assert p(r'"a\"b"') == ast.StrLit('a"b')
    assert p(r'"back\\slash"') == ast.StrLit("back\\slash")
    assert p(r'"tab\tend"') == ast.StrLit("tab\tend")


def test_errors() -> None:
    with pytest.raises(MathQLError):
        p("1 +")
    with pytest.raises(MathQLError):
        p("(1 + 2).x")  # field access on a non-variable
    with pytest.raises(MathQLError):
        p(r'"bad\q"')  # invalid escape
