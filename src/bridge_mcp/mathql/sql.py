"""The SQL expression syntax and its rendering to SQLite text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, Direction, UnaryOp


@dataclass(frozen=True)
class Col:
    table: str
    column: str


@dataclass(frozen=True)
class IntLit:
    value: int


@dataclass(frozen=True)
class StrLit:
    value: str


@dataclass(frozen=True)
class BoolLit:
    value: bool


@dataclass(frozen=True)
class Null:
    pass


@dataclass(frozen=True)
class UnOp:
    op: UnaryOp
    expr: Expr


@dataclass(frozen=True)
class BinOp:
    op: BinaryOp
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Compare:
    op: ComparisonOp
    left: Expr
    right: Expr


@dataclass(frozen=True)
class IsNull:
    expr: Expr


@dataclass(frozen=True)
class IsNotNull:
    expr: Expr


@dataclass(frozen=True)
class Case:
    cond: Expr
    then_: Expr
    else_: Expr


@dataclass(frozen=True)
class JsonArray:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class JsonExtract:
    expr: Expr
    index: int


Expr = (
    Col
    | IntLit
    | StrLit
    | BoolLit
    | Null
    | UnOp
    | BinOp
    | Compare
    | IsNull
    | IsNotNull
    | Case
    | JsonArray
    | JsonExtract
)


def render_unary_op(op: UnaryOp) -> str:
    match op:
        case UnaryOp.NOT:
            return "NOT"
        case UnaryOp.NEG:
            return "-"
    assert_never(op)


def render_binary_op(op: BinaryOp) -> str:
    match op:
        case BinaryOp.AND:
            return "AND"
        case BinaryOp.OR:
            return "OR"
        case BinaryOp.ADD:
            return "+"
        case BinaryOp.SUB:
            return "-"
        case BinaryOp.MUL:
            return "*"
    assert_never(op)


def render_comparison_op(op: ComparisonOp) -> str:
    match op:
        case ComparisonOp.EQ:
            return "="
        case ComparisonOp.NE:
            return "<>"
        case ComparisonOp.LT:
            return "<"
        case ComparisonOp.LE:
            return "<="
        case ComparisonOp.GT:
            return ">"
        case ComparisonOp.GE:
            return ">="
    assert_never(op)


def render_direction(direction: Direction) -> str:
    match direction:
        case Direction.ASC:
            return "ASC"
        case Direction.DESC:
            return "DESC"
    assert_never(direction)


def render(e: Expr) -> str:
    """Render a SQL expression to SQLite text.

    String literals are single-quoted, with `''` escaping an embedded quote.
    """
    match e:
        case Col(table, column):
            return f"{table}.{column}"
        case IntLit(value):
            return str(value)
        case BoolLit(value):
            return "1" if value else "0"
        case StrLit(value):
            return "'" + value.replace("'", "''") + "'"
        case Null():
            return "NULL"
        case UnOp(op, expr):
            return f"{render_unary_op(op)} ({render(expr)})"
        case BinOp(op, left, right):
            return f"({render(left)} {render_binary_op(op)} {render(right)})"
        case Compare(op, left, right):
            return f"({render(left)} {render_comparison_op(op)} {render(right)})"
        case IsNull(expr):
            return f"({render(expr)} IS NULL)"
        case IsNotNull(expr):
            return f"({render(expr)} IS NOT NULL)"
        case Case(cond, then_, else_):
            return f"(CASE WHEN {render(cond)} THEN {render(then_)} ELSE {render(else_)} END)"
        case JsonArray(items):
            return f"json_array({', '.join(render(item) for item in items)})"
        case JsonExtract(expr, index):
            return f"json_extract({render(expr)}, '$[{index}]')"
    assert_never(e)
