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
class Ref:
    """An output-column alias; meaningful only in ORDER BY position."""

    name: str


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
class IsTrue:
    """True when the expression is true; false when it is false or NULL."""

    expr: Expr


@dataclass(frozen=True)
class IsNotFalse:
    """True when the expression is true or NULL; false when it is false."""

    expr: Expr


@dataclass(frozen=True)
class Case:
    cond: Expr
    then_: Expr
    else_: Expr


@dataclass(frozen=True)
class Call:
    """A SQL function applied to arguments."""

    name: str
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class Json:
    """A `json` call: the canonical (minified) text of a JSON value."""

    expr: Expr


@dataclass(frozen=True)
class JsonArray:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class JsonExtract:
    expr: Expr
    index: int


Expr = (
    Col
    | Ref
    | IntLit
    | StrLit
    | BoolLit
    | Null
    | UnOp
    | BinOp
    | Compare
    | IsNull
    | IsNotNull
    | IsTrue
    | IsNotFalse
    | Case
    | Call
    | Json
    | JsonArray
    | JsonExtract
)


def json_array(items: tuple[Expr, ...]) -> Expr:
    """A `json_array` of `items`, elided when there is exactly one."""
    match items:
        case (single,):
            return single
        case _:
            return JsonArray(items)


def is_constant(e: Expr) -> bool:
    """Does the expression take the same value in every row?"""
    match e:
        case IntLit() | StrLit() | BoolLit() | Null():
            return True
        case Col() | Ref() | Call():
            return False
        case UnOp(_, operand) | IsNull(operand) | IsNotNull(operand) | Json(operand):
            return is_constant(operand)
        case IsTrue(operand) | IsNotFalse(operand):
            return is_constant(operand)
        case JsonExtract(operand, _):
            return is_constant(operand)
        case BinOp(_, left, right) | Compare(_, left, right):
            return is_constant(left) and is_constant(right)
        case Case(cond, then_, else_):
            return is_constant(cond) and is_constant(then_) and is_constant(else_)
        case JsonArray(items):
            return all(is_constant(item) for item in items)
    assert_never(e)


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
        case BinaryOp.DIV:
            return "/"
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


def render_ident(name: str) -> str:
    """Render an identifier, double-quoted, an embedded quote doubled."""
    return '"' + name.replace('"', '""') + '"'


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
            return f"{table}.{render_ident(column)}"
        case Ref(name):
            return name
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
        case IsTrue(expr):
            return f"({render(expr)} IS TRUE)"
        case IsNotFalse(expr):
            return f"({render(expr)} IS NOT FALSE)"
        case Case(cond, then_, else_):
            return f"(CASE WHEN {render(cond)} THEN {render(then_)} ELSE {render(else_)} END)"
        case Call(name, args):
            return f"{render_ident(name)}({', '.join(render(arg) for arg in args)})"
        case Json(expr):
            return f"json({render(expr)})"
        case JsonArray(items):
            return f"json_array({', '.join(render(item) for item in items)})"
        case JsonExtract(expr, index):
            return f"json_extract({render(expr)}, '$[{index}]')"
    assert_never(e)


@dataclass(frozen=True)
class Join:
    """A hoisted `LEFT JOIN`: the table, its alias, and the columnwise equalities
    `alias.column = expr` that form the `ON` condition."""

    table: str
    alias: str
    equalities: tuple[tuple[str, Expr], ...]


@dataclass(frozen=True)
class Query:
    """A SQL `SELECT` query: the `FROM` tables with their aliases, the hoisted joins,
    the output columns each with its alias, the boolean condition, the ordering, and
    the limit."""

    froms: tuple[tuple[str, str], ...]
    joins: tuple[Join, ...]
    output: tuple[tuple[Expr, str], ...]
    cond: Expr
    order: tuple[tuple[Expr, Direction], ...]
    limit: int | None


def _render_join(join: Join) -> str:
    conditions = [
        f"{join.alias}.{render_ident(column)} = {render(e)}" for column, e in join.equalities
    ]
    on = " AND ".join(conditions) if conditions else "1"
    return f" LEFT JOIN {render_ident(join.table)} AS {join.alias} ON {on}"


def _render_from(q: Query) -> str:
    """The `FROM` clause: the tables with their aliases, absent for a query over no
    table, and `(SELECT 1)` where a hoisted join stands over no table."""
    if q.froms:
        return " FROM " + ", ".join(
            f"{render_ident(table)} AS {alias}" for table, alias in q.froms
        )
    elif q.joins:
        return " FROM (SELECT 1)"
    else:
        return ""


def render_query(q: Query) -> str:
    """Render a query to SQLite text, with a bare condition. Each output column is
    rendered as `<expr> AS <alias>`; a hoisted join renders as `LEFT JOIN`, so when it
    matches no row its columns are NULL. A query naming no output column selects `1`."""
    joins = "".join(_render_join(join) for join in q.joins)
    columns = (
        ", ".join(f"{render(e)} AS {alias}" for e, alias in q.output) if q.output else "1"
    )
    order = (
        " ORDER BY " + ", ".join(f"{render(e)} {render_direction(d)}" for e, d in q.order)
        if q.order
        else ""
    )
    limit = f" LIMIT {q.limit}" if q.limit is not None else ""
    return f"SELECT {columns}{_render_from(q)}{joins} WHERE {render(q.cond)}{order}{limit}"
