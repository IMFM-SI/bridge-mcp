"""Execute a type-checked query against a SQLite connection, producing JSON rows.

The condition, the output and the order reach the database as SQL. The postprocess
entries are evaluated here, over each decoded row.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, assert_never

from bridge_mcp.mathql import expr, query, sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.database import Database, PostFunction
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, UnaryOp
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query
from bridge_mcp.mathql.types import (
    BoolType,
    IntType,
    ListType,
    ProductType,
    StringType,
    Ty,
)


def database_path() -> Path:
    """The bundled `math_data` database, or the path in `BRIDGE_MCP_DB` if set."""
    override = os.environ.get("BRIDGE_MCP_DB")
    if override is not None:
        return Path(override)
    else:
        return Path(
            str(resources.files("bridge_mcp.mathql.databases").joinpath("math-data.db"))
        )


def _decode_cell(ty: Ty, cell: Any) -> object:
    """Decode one output cell at its declared type; a NULL cell is None. Lists and
    products are stored as JSON text and returned decoded."""
    if cell is None:
        return None
    else:
        match ty:
            case IntType():
                return int(cell)
            case BoolType():
                return bool(cell)
            case StringType():
                return str(cell)
            case ListType() | ProductType():
                try:
                    return json.loads(cell)
                except json.JSONDecodeError as error:
                    raise MathQLError(
                        f"expected JSON in a list or product column: {error}"
                    ) from error
        assert_never(ty)


def canonical(value: object) -> str:
    """The canonical JSON text of a value, as SQLite's `json` renders it: no spaces,
    non-ASCII characters left as themselves, object keys sorted."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _as_int(value: object) -> int:
    """`value` as an integer. A boolean is no integer, though `bool` subclasses `int`."""
    if type(value) is int:
        return value
    else:
        raise MathQLError(f"expected an integer, got {value!r}")


def _as_bool(value: object) -> bool:
    if type(value) is bool:
        return value
    else:
        raise MathQLError(f"expected a boolean, got {value!r}")


def _as_str(value: object) -> str:
    if type(value) is str:
        return value
    else:
        raise MathQLError(f"expected a string, got {value!r}")


def _eval_unary_op(op: UnaryOp, value: object) -> object:
    match op:
        case UnaryOp.NOT:
            return not _as_bool(value)
        case UnaryOp.NEG:
            return -_as_int(value)
    assert_never(op)


def _eval_binary_op(op: BinaryOp, left: object, right: object) -> object:
    """`&&` and `||` are strict: each coerces both operands, so an operand that is no
    boolean makes the whole expression fail."""
    match op:
        case BinaryOp.AND:
            return _as_bool(left) & _as_bool(right)
        case BinaryOp.OR:
            return _as_bool(left) | _as_bool(right)
        case BinaryOp.ADD:
            return _as_int(left) + _as_int(right)
        case BinaryOp.SUB:
            return _as_int(left) - _as_int(right)
        case BinaryOp.MUL:
            return _as_int(left) * _as_int(right)
    assert_never(op)


def _comparison_keys(ty: Ty, left: object, right: object) -> tuple[Any, Any]:
    """The pair of values a comparison at `ty` compares. A list or a product compares by
    canonical JSON text, which is how SQLite compares `json(a)` to `json(b)`."""
    match ty:
        case IntType():
            return _as_int(left), _as_int(right)
        case BoolType():
            return _as_bool(left), _as_bool(right)
        case StringType():
            return _as_str(left), _as_str(right)
        case ListType() | ProductType():
            return canonical(left), canonical(right)
    assert_never(ty)


def _eval_comparison(op: ComparisonOp, ty: Ty, left: object, right: object) -> object:
    """Compare at `ty`. An absent operand makes the comparison absent, as in SQL."""
    if left is None or right is None:
        return None
    else:
        a, b = _comparison_keys(ty, left, right)
        match op:
            case ComparisonOp.EQ:
                return bool(a == b)
            case ComparisonOp.NE:
                return bool(a != b)
            case ComparisonOp.LT:
                return bool(a < b)
            case ComparisonOp.LE:
                return bool(a <= b)
            case ComparisonOp.GT:
                return bool(a > b)
            case ComparisonOp.GE:
                return bool(a >= b)
        assert_never(op)


@dataclass(frozen=True)
class PostEnvironment:
    """A postprocess entry's environment: the values bound so far, and the functions the
    database makes callable there."""

    values: Mapping[str, object]
    functions: Mapping[str, PostFunction]

    def extend(self, name: str, value: object) -> PostEnvironment:
        return PostEnvironment({**self.values, name: value}, self.functions)


def _apply(env: PostEnvironment, name: str, args: tuple[object, ...]) -> object:
    """Apply a postprocess function, reporting whatever the implementation raises as a
    `MathQLError`."""
    match env.functions.get(name):
        case None:
            raise MathQLError(f"unknown function {name}")
        case function:
            try:
                return function.implementation(args)
            except MathQLError:
                raise
            except Exception as error:
                raise MathQLError(f"{name} failed: {error}") from error


def eval_post_expr(env: PostEnvironment, e: expr.Expr) -> object:
    """Evaluate a postprocess expression over the values in `env`."""
    match e:
        case expr.IntLit(value):
            return value
        case expr.BoolLit(value):
            return value
        case expr.StrLit(value):
            return value
        case expr.Ident(name):
            if name in env.values:
                return env.values[name]
            else:
                raise MathQLError(f"unknown identifier {name}")
        case expr.Id():
            raise MathQLError("id belongs to the compiled clauses, not to postprocess")
        case expr.Field():
            raise MathQLError("a field projection belongs to the compiled clauses")
        case expr.Call(name, args):
            return _apply(env, name, tuple(eval_post_expr(env, arg) for arg in args))
        case expr.UnOp(op, operand):
            return _eval_unary_op(op, eval_post_expr(env, operand))
        case expr.BinOp(op, left, right):
            return _eval_binary_op(op, eval_post_expr(env, left), eval_post_expr(env, right))
        case expr.Compare(op, ty, left, right):
            return _eval_comparison(
                op, ty, eval_post_expr(env, left), eval_post_expr(env, right)
            )
        case expr.ListExpr(items) | expr.TupleExpr(items):
            return [eval_post_expr(env, item) for item in items]
        case expr.Proj(operand, index):
            match eval_post_expr(env, operand):
                case list() as components if 0 <= index < len(components):
                    return components[index]
                case other:
                    raise MathQLError(f"no component {index} in {other!r}")
        case expr.Ite(cond, then_, else_):
            if _as_bool(eval_post_expr(env, cond)):
                return eval_post_expr(env, then_)
            else:
                return eval_post_expr(env, else_)
        case expr.Defined(operand):
            return _is_defined(env, operand)
        case expr.Undefined(operand):
            return not _is_defined(env, operand)
    assert_never(e)


def _is_defined(env: PostEnvironment, e: expr.Expr) -> bool:
    """Whether `e` evaluates to a value other than absent. A failed evaluation counts as
    absent, so `defined` and `undefined` answer as `IS NOT NULL` and `IS NULL` do."""
    try:
        return eval_post_expr(env, e) is not None
    except MathQLError:
        return False


def eval_postprocess(
    env: PostEnvironment, columns: Sequence[query.OutputColumn]
) -> list[tuple[str, object]]:
    """Evaluate the postprocess entries in order, each in the environment of the earlier
    ones. An entry whose evaluation fails has the value None."""
    match columns:
        case []:
            return []
        case [column, *rest]:
            try:
                value = eval_post_expr(env, column.expr)
            except Exception:
                value = None
            return [
                (column.name, value),
                *eval_postprocess(env.extend(column.name, value), rest),
            ]
    raise AssertionError("unreachable")


def _decode_row(q: query.Query, row: Sequence[Any]) -> list[tuple[str, object]]:
    """One row's output cells, each paired with its column name, in output order. A query
    naming no output column selects a placeholder, which is passed over here."""
    if q.output:
        return [
            (column.name, _decode_cell(column.ty, cell))
            for column, cell in zip(q.output, row, strict=True)
        ]
    else:
        return []


def _row(
    q: query.Query, functions: Mapping[str, PostFunction], row: Sequence[Any]
) -> list[tuple[str, object]]:
    """One result row: its output cells, then its postprocess entries."""
    output = _decode_row(q, row)
    return output + eval_postprocess(PostEnvironment(dict(output), functions), q.postprocess)


def run(
    connection: sqlite3.Connection, database: Database, q: query.Query
) -> list[list[tuple[str, object]]]:
    """Run a type-checked query, returning each row as its list of name/value pairs."""
    rendered = sql.render_query(compile_query(database, q))
    functions = {f.name: f for f in database.post_functions}
    return [_row(q, functions, row) for row in connection.execute(rendered).fetchall()]


def run_query(
    connection: sqlite3.Connection, database: Database, request: Mapping[str, Any]
) -> list[list[tuple[str, object]]]:
    """Parse, type-check, compile, and run a query from its JSON form."""
    return run(connection, database, check_query(database, from_json(request)))
