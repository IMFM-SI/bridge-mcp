"""Checks for the expression parser. Spans are excluded from equality."""

import pytest

from bridge_mcp.mathql import input as ast
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, UnaryOp
from bridge_mcp.mathql.parser import parse_expression as p
from bridge_mcp.mathql.parser import parse_identifier


def test_atoms() -> None:
    assert p("42") == ast.IntLit(42)
    assert p("true") == ast.BoolLit(True)
    assert p("false") == ast.BoolLit(False)
    assert p("'hi'") == ast.StrLit("hi")
    assert p("x") == ast.Ident("x")
    assert p("trueish") == ast.Ident("trueish")
    assert p("g.n") == ast.Field(ast.Ident("g"), "n")


def test_id_and_obj() -> None:
    assert p("id(g)") == ast.Id(ast.Ident("g"))
    assert p("id g.link") == ast.Id(ast.Field(ast.Ident("g"), "link"))
    assert p("Graph['abc']") == ast.Obj("Graph", (ast.StrLit("abc"),))
    assert p("Pair[1, 2]") == ast.Obj("Pair", (ast.IntLit(1), ast.IntLit(2)))
    assert p("Unit[]") == ast.Obj("Unit", ())
    assert p("Graph['abc'].n") == ast.Field(ast.Obj("Graph", (ast.StrLit("abc"),)), "n")


def test_field_chains() -> None:
    assert p("m.skeleton.n") == ast.Field(ast.Field(ast.Ident("m"), "skeleton"), "n")
    assert p("(1 + 2).x") == ast.Field(
        ast.BinOp(BinaryOp.ADD, ast.IntLit(1), ast.IntLit(2)), "x"
    )


def test_precedence() -> None:
    assert p("g.planar && g.n > 0") == ast.BinOp(
        BinaryOp.AND,
        ast.Field(ast.Ident("g"), "planar"),
        ast.Compare(ComparisonOp.GT, ast.Field(ast.Ident("g"), "n"), ast.IntLit(0)),
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
    assert p("(g.n)") == ast.Field(ast.Ident("g"), "n")  # grouping, not a tuple
    assert p("(g.n, g.planar)") == ast.TupleExpr(
        (ast.Field(ast.Ident("g"), "n"), ast.Field(ast.Ident("g"), "planar"))
    )
    assert p("(g.n, g.planar).0") == ast.Proj(
        ast.TupleExpr((ast.Field(ast.Ident("g"), "n"), ast.Field(ast.Ident("g"), "planar"))),
        0,
    )


def test_conditional_and_presence() -> None:
    assert p("if g.planar then 1 else 2") == ast.Ite(
        ast.Field(ast.Ident("g"), "planar"), ast.IntLit(1), ast.IntLit(2)
    )
    assert p("defined g.n") == ast.Defined(ast.Field(ast.Ident("g"), "n"))
    assert p("!g.planar") == ast.UnOp(UnaryOp.NOT, ast.Field(ast.Ident("g"), "planar"))


def test_utf8_operators() -> None:
    assert p("g.n ≤ 3") == ast.Compare(
        ComparisonOp.LE, ast.Field(ast.Ident("g"), "n"), ast.IntLit(3)
    )
    assert p("a ∧ b") == ast.BinOp(BinaryOp.AND, ast.Ident("a"), ast.Ident("b"))


def test_span_is_recorded_but_ignored_in_equality() -> None:
    parsed = p("42")
    assert parsed.span is not None
    assert parsed == ast.IntLit(42)  # span defaults to None on the right; still equal


def test_string_literals() -> None:
    assert p("'it''s'") == ast.StrLit("it's")
    assert p("''") == ast.StrLit("")
    assert p("'a' == 'b'") == ast.Compare(ComparisonOp.EQ, ast.StrLit("a"), ast.StrLit("b"))


def test_identifiers() -> None:
    assert parse_identifier("graph6") == "graph6"
    with pytest.raises(MathQLError):
        parse_identifier("defined")  # keyword
    with pytest.raises(MathQLError):
        parse_identifier("_x")  # no leading underscore
    with pytest.raises(MathQLError):
        parse_identifier("g.n")  # not a plain identifier


def test_errors() -> None:
    with pytest.raises(MathQLError):
        p("1 +")
    with pytest.raises(MathQLError):
        p('"hi"')  # double quotes are not string literals
    with pytest.raises(MathQLError):
        p("'unterminated")
