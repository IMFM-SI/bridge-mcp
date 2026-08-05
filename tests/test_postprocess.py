"""Checks for evaluating the postprocess clause, over rows supplied directly."""

import functools
import json
import sqlite3

import pytest

from bridge_mcp.mathql import expr
from bridge_mcp.mathql.context import Context
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import (
    PostEnvironment,
    canonical,
    eval_post_expr,
    eval_postprocess,
)
from bridge_mcp.mathql.operators import ComparisonOp
from bridge_mcp.mathql.parser import parse_expression
from bridge_mcp.mathql.query import OutputColumn
from bridge_mcp.mathql.typecheck import infer
from bridge_mcp.mathql.types import (
    BoolType,
    IntType,
    ListType,
    ProductType,
    StringType,
    Ty,
)
from tests.toy import DATABASE as TOY

FUNCTIONS = {f.name: f for f in TOY.post_functions}

Row = list[tuple[str, object]]


def _declared(value: object, ty: Ty | None) -> Ty:
    """The type a supplied row value stands at."""
    match ty, value:
        case (declared, _) if declared is not None:
            return declared
        case (_, bool()):
            return BoolType()
        case (_, int()):
            return IntType()
        case (_, str()):
            return StringType()
        case _:
            return ListType(IntType())


def _post(row: Row, entries: list[tuple[str, str]], ty: Ty | None = None) -> Row:
    """Type-check the entries against the row's column types, then evaluate them over the
    row's values. `ty` overrides the type read off the values, for an absent one."""
    ctx: Context = functools.reduce(
        lambda c, column: c.extend_ident(column[0], _declared(column[1], ty)),
        row,
        TOY.post_context(),
    )
    columns: list[OutputColumn] = []
    for name, source in entries:
        column_ty, elaborated = infer(ctx, parse_expression(source))
        columns.append(OutputColumn(name, column_ty, elaborated))
        ctx = ctx.extend_ident(name, column_ty)
    return eval_postprocess(PostEnvironment(dict(row), FUNCTIONS), columns)


def _compare(op: ComparisonOp, ty: Ty, left: object, right: object) -> object:
    """Evaluate a comparison at `ty` through the evaluator."""
    return eval_post_expr(
        PostEnvironment({"a": left, "b": right}, FUNCTIONS),
        expr.Compare(op, ty, expr.Ident("a"), expr.Ident("b")),
    )


# --- entries ---


def test_a_call_runs_over_the_row() -> None:
    assert _post([("n", 5)], [("k", "plus(n, 1)")]) == [("k", 6)]


def test_an_entry_sees_the_earlier_values() -> None:
    assert _post([("n", 5)], [("k", "plus(n, 1)"), ("m", "k * 2")]) == [("k", 6), ("m", 12)]


def test_a_failed_entry_is_absent_and_absence_spreads() -> None:
    row: Row = [("n", "not a number")]
    assert _post(row, [("k", "plus(n, 1)"), ("m", "k * 2")], IntType()) == [
        ("k", None),
        ("m", None),
    ]


def test_arithmetic() -> None:
    assert _post([("n", 5)], [("k", "n * 2 - 1"), ("m", "-n")]) == [("k", 9), ("m", -5)]


def test_logic_evaluates_both_operands() -> None:
    assert _post([("b", True)], [("k", "!b"), ("m", "b || false")]) == [
        ("k", False),
        ("m", True),
    ]
    # `false && …` still evaluates the right operand, so an absent one is absent.
    assert _post([("n", None)], [("k", "false && n > 0")], IntType()) == [("k", None)]


def test_conditionals_lists_and_projections() -> None:
    assert _post([("n", 5)], [("k", "if n > 3 then 1 else 0")]) == [("k", 1)]
    assert _post([("n", 5)], [("k", "[n, n]")]) == [("k", [5, 5])]
    assert _post([("n", 5)], [("k", "(n, 1).0")]) == [("k", 5)]


# --- comparison ---


def test_comparison_at_each_type() -> None:
    pair = ProductType((IntType(), StringType()))
    assert _compare(ComparisonOp.LT, IntType(), 2, 10) is True
    assert _compare(ComparisonOp.LT, BoolType(), False, True) is True
    assert _compare(ComparisonOp.LT, StringType(), "Z", "a") is True
    assert _compare(ComparisonOp.EQ, pair, [1, "a"], [1, "a"]) is True
    assert _compare(ComparisonOp.NE, pair, [1, "a"], [1, "b"]) is True


def test_a_list_compares_by_canonical_text() -> None:
    assert _compare(ComparisonOp.GT, ListType(IntType()), [2, 2], [2, 10]) is True
    assert [2, 2] < [2, 10]  # Python's elementwise answer runs the other way


def test_an_absent_operand_makes_the_comparison_absent() -> None:
    assert _compare(ComparisonOp.LT, IntType(), None, 5) is None
    assert _compare(ComparisonOp.EQ, StringType(), "a", None) is None


def test_a_list_comparison_through_the_whole_stage() -> None:
    assert _post([("d", [2, 2])], [("b", "d == [2, 2]")]) == [("b", True)]


def test_a_boolean_is_no_integer() -> None:
    with pytest.raises(MathQLError):
        _compare(ComparisonOp.LT, IntType(), True, 2)
    assert _post([("b", True)], [("k", "plus(b, 1)")], IntType()) == [("k", None)]


# --- absence ---


def test_defined_and_undefined() -> None:
    assert _post([("n", 5)], [("a", "defined n"), ("b", "undefined n")]) == [
        ("a", True),
        ("b", False),
    ]
    assert _post([("n", None)], [("a", "defined n"), ("b", "undefined n")], IntType()) == [
        ("a", False),
        ("b", True),
    ]
    assert _post(
        [("n", "not a number")],
        [("a", "defined plus(n, 1)"), ("b", "undefined plus(n, 1)")],
        IntType(),
    ) == [("a", False), ("b", True)]


def test_a_projection_outside_the_range() -> None:
    env = PostEnvironment({"d": [1, 2]}, FUNCTIONS)
    assert eval_post_expr(env, expr.Proj(expr.Ident("d"), 1)) == 2
    with pytest.raises(MathQLError):
        eval_post_expr(env, expr.Proj(expr.Ident("d"), 5))
    with pytest.raises(MathQLError):
        eval_post_expr(env, expr.Proj(expr.Ident("d"), -1))


def test_the_compiled_forms_stay_out_of_postprocess() -> None:
    env = PostEnvironment({}, FUNCTIONS)
    with pytest.raises(MathQLError):
        eval_post_expr(env, expr.Id(expr.DomainIdent("g")))
    with pytest.raises(MathQLError):
        eval_post_expr(env, expr.Field(expr.DomainIdent("g"), "n"))


# --- canonical text ---


VALUES: list[object] = [
    [2, 2],
    [2, 10],
    [True, False],
    [],
    [[1], [2, 3]],
    [-1, 0],
    ["it's"],
    ["a\nb\t"],
    ["été"],
]


def test_canonical_text_survives_sqlite_json() -> None:
    """A comparison in postprocess reads the canonical text of a decoded value, while the
    same comparison in a condition reads `json()` of the stored text. The two agree when
    the canonical text is what `json()` returns for it."""
    with sqlite3.connect(":memory:") as connection:
        for value in VALUES:
            text = canonical(value)
            (rendered,) = connection.execute("SELECT json(?)", (text,)).fetchone()
            assert rendered == text, value


def test_canonical_text_matches_the_stored_form() -> None:
    """The generator stores a list column as minified JSON; `json()` of that text is what
    the canonical form of the decoded value must equal."""
    with sqlite3.connect(":memory:") as connection:
        for value in VALUES:
            stored = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            (rendered,) = connection.execute("SELECT json(?)", (stored,)).fetchone()
            assert canonical(json.loads(stored)) == rendered, value
