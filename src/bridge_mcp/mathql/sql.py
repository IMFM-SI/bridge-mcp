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
    | Case
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
        case Case(cond, then_, else_):
            return f"(CASE WHEN {render(cond)} THEN {render(then_)} ELSE {render(else_)} END)"
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
    conditions = [f"{join.alias}.{column} = {render(e)}" for column, e in join.equalities]
    on = " AND ".join(conditions) if conditions else "1"
    return f" LEFT JOIN {join.table} AS {join.alias} ON {on}"


def render_query(q: Query) -> str:
    """Render a query to SQLite text, with a bare condition. Each output column is
    rendered as `<expr> AS <alias>`; a hoisted join renders as `LEFT JOIN`, so when it
    matches no row its columns are NULL."""
    froms = ", ".join(f"{table} AS {alias}" for table, alias in q.froms)
    joins = "".join(_render_join(join) for join in q.joins)
    columns = ", ".join(f"{render(e)} AS {alias}" for e, alias in q.output)
    order = (
        " ORDER BY " + ", ".join(f"{render(e)} {render_direction(d)}" for e, d in q.order)
        if q.order
        else ""
    )
    limit = f" LIMIT {q.limit}" if q.limit is not None else ""
    return f"SELECT {columns} FROM {froms}{joins} WHERE {render(q.cond)}{order}{limit}"
