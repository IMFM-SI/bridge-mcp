"""Execute a type-checked query against a SQLite connection, producing JSON rows.

The condition, the output and the order reach the database as SQL. The postprocess
entries are evaluated here, over each decoded row.
"""

from __future__ import annotations

import functools
import json
import os
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, assert_never

from bridge_mcp.mathql import expr, query, sql
from bridge_mcp.mathql.compile import Mode, compile_query
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
    """A value as minified JSON text in UTF-8, with object keys in sorted order."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _as_int(value: object) -> int:
    """`value` as an integer, which a boolean is not."""
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


def _encode_cell(ty: Ty, value: object) -> int | str | None:
    """A value as SQLite stores it at `ty`, the inverse of `_decode_cell`: a boolean as 0
    or 1, a list or a product as JSON text, and None as NULL."""
    if value is None:
        return None
    else:
        match ty:
            case IntType():
                return _as_int(value)
            case BoolType():
                return int(_as_bool(value))
            case StringType():
                return _as_str(value)
            case ListType() | ProductType():
                return canonical(value)
        assert_never(ty)


def _as_sql_function(
    arg_types: Sequence[Ty],
    result_ty: Ty,
    implementation: Callable[[Sequence[object]], object],
) -> Callable[..., int | str | None]:
    """An implementation as SQLite calls it: on the stored argument values, returning the
    stored result. A failure yields NULL, as it yields an absent value in postprocess, so
    a row on which the function is undefined does not abort the query."""

    def call(*cells: object) -> int | str | None:
        try:
            args = [_decode_cell(ty, cell) for ty, cell in zip(arg_types, cells, strict=True)]
            return _encode_cell(result_ty, implementation(args))
        except Exception:  # noqa: BLE001 - whatever escapes here aborts the whole query
            return None

    return call


def _eval_unary_op(op: UnaryOp, value: object) -> object:
    match op:
        case UnaryOp.NOT:
            return not _as_bool(value)
        case UnaryOp.NEG:
            return -_as_int(value)
    assert_never(op)


def _quotient(left: int, right: int) -> int:
    """The quotient truncated toward zero, as SQLite's `/` computes it. A zero divisor
    has no quotient; the failure raised here reaches the caller as an absent value, which
    is what SQLite yields there."""
    if right == 0:
        raise MathQLError("division by zero")
    magnitude = abs(left) // abs(right)
    return -magnitude if (left < 0) != (right < 0) else magnitude


def _eval_binary_op(op: BinaryOp, left: object, right: object) -> object:
    """Apply a binary operator to two evaluated operands, coercing both."""
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
        case BinaryOp.DIV:
            return _quotient(_as_int(left), _as_int(right))
    assert_never(op)


def _comparison_keys(ty: Ty, left: object, right: object) -> tuple[Any, Any]:
    """The pair of values a comparison at `ty` compares: the coerced scalars, or the
    canonical text of a list or a product."""
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
    """Compare at `ty`; an absent operand makes the comparison absent."""
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
    """Whether `e` evaluates to a value other than absent, a failed evaluation counting
    as absent."""
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
    """One row's output cells, each paired with its column name, in output order."""
    if q.output:
        return [
            (column.name, _decode_cell(column.ty, cell))
            for column, cell in zip(q.output, row, strict=True)
        ]
    else:
        return []


CERTAIN = "certain"
"""The name of the column that says, in complete mode, whether a row matches for
certain."""


def _row(
    q: query.Query, functions: Mapping[str, PostFunction], mode: Mode, row: Sequence[Any]
) -> list[tuple[str, object]]:
    """One result row: its output cells, in complete mode whether it matches for certain,
    then its postprocess entries."""
    match mode:
        case "sound":
            cells, marker = row, []
        case "complete":
            cells, marker = row[:-1], [(CERTAIN, bool(row[-1]))]
    output = _decode_row(q, cells)
    post = eval_postprocess(PostEnvironment(dict(output), functions), q.postprocess)
    return output + marker + post


def _column_names(connection: sqlite3.Connection, table: str) -> list[str]:
    """The names of the columns of `table`, read with a query so that a connection
    restricted to queries can answer it."""
    cursor = connection.execute(f"SELECT * FROM {sql.render_ident(table)} LIMIT 0")
    return [description[0] for description in cursor.description or []]


def _tables(connection: sqlite3.Connection) -> set[str]:
    """The names of the tables the database holds."""
    statement = "SELECT name FROM sqlite_master WHERE type = 'table'"
    return {row[0] for row in connection.execute(statement).fetchall()}


def safe_alias_predicate(
    connection: sqlite3.Connection, database: Database
) -> Callable[[str], bool]:
    """A name is a safe alias when no table of `database` has a column of that name.
    `rowid`, `oid` and `_rowid_` name a column that `SELECT *` omits."""
    present = _tables(connection)
    columns = (
        name
        for schema in database.domains.values()
        if schema.table in present
        for name in _column_names(connection, schema.table)
    )
    taken = {name.lower() for name in columns} | {"rowid", "oid", "_rowid_"}
    return lambda name: name.lower() not in taken


_CACHE_SIZE = 256
"""How many recent results each registered function remembers."""


def register_functions(connection: sqlite3.Connection, database: Database) -> None:
    """Make each SQL function of `database` that has an implementation callable on
    `connection`, under its SQL name. Each remembers its recent results, so a call
    SQLite repeats on one row, as a complete query does for its marker, or as a query
    calling the same function in two clauses does, is computed once."""
    for function in database.sql_functions:
        if function.implementation is not None:
            wrapper = _as_sql_function(
                function.arg_types, function.result_ty, function.implementation
            )
            connection.create_function(
                function.sql_name,
                len(function.arg_types),
                functools.lru_cache(maxsize=_CACHE_SIZE)(wrapper),
                deterministic=True,
            )


TIME_LIMIT = 30.0
"""How many seconds a query may run before the database stops it."""

# The moment at which the query running on this thread is to stop, or None when no query
# is running on it. Per thread, since each tool call runs on a thread of its own and the
# threads share one connection.
_deadline = threading.local()


def _past_deadline() -> bool:
    """Whether the query running on this thread has run past its deadline."""
    at: float | None = getattr(_deadline, "at", None)
    return at is not None and time.monotonic() > at


def limit_time(connection: sqlite3.Connection) -> None:
    """Stop a query running on `connection` once the deadline `run` set for it has
    passed. SQLite asks every thousand steps of its work; a statement run other than by
    `run` has no deadline and is never stopped."""
    connection.set_progress_handler(_past_deadline, 1000)


@dataclass(frozen=True)
class Answer:
    """The rows a query returns, each its list of name/value pairs, and whether the time
    limit stopped the query first. The rows of a stopped query each match it; the rows
    it did not reach yet are missing."""

    rows: list[list[tuple[str, object]]]
    truncated: bool


def compiled_sql(
    database: Database,
    is_safe_alias: Callable[[str], bool],
    q: query.Query,
    mode: Mode = "sound",
) -> str:
    """The SQL SELECT statement a type-checked query compiles to. The postprocess entries
    have no SQL image and leave no trace in it."""
    return sql.render_query(compile_query(database, is_safe_alias, q, mode))


def compiled_sql_query(
    database: Database,
    is_safe_alias: Callable[[str], bool],
    request: Mapping[str, Any],
    mode: Mode = "sound",
) -> str:
    """Parse, type-check and compile a query from its JSON form, returning its SQL."""
    q = check_query(database, from_json(request))
    return compiled_sql(database, is_safe_alias, q, mode)


def run(
    connection: sqlite3.Connection,
    database: Database,
    is_safe_alias: Callable[[str], bool],
    q: query.Query,
    mode: Mode = "sound",
) -> Answer:
    """Run a type-checked query within `TIME_LIMIT` seconds, on a connection `limit_time`
    was applied to. Past the limit, the rows read so far are returned, marked
    truncated."""
    names = [column.name for column in (*q.output, *q.postprocess)]
    if mode == "complete" and CERTAIN in names:
        raise MathQLError(f"in complete mode the column name {CERTAIN} is reserved")
    rendered = compiled_sql(database, is_safe_alias, q, mode)
    functions = {f.name: f for f in database.post_functions}
    rows: list[list[tuple[str, object]]] = []
    _deadline.at = time.monotonic() + TIME_LIMIT
    try:
        for row in connection.execute(rendered):
            rows.append(_row(q, functions, mode, row))
    except sqlite3.OperationalError as error:
        if str(error) == "interrupted":
            return Answer(rows, truncated=True)
        else:
            raise
    finally:
        _deadline.at = None
    return Answer(rows, truncated=False)


def run_query(
    connection: sqlite3.Connection,
    database: Database,
    is_safe_alias: Callable[[str], bool],
    request: Mapping[str, Any],
    mode: Mode = "sound",
) -> Answer:
    """Parse, type-check, compile, and run a query from its JSON form."""
    q = check_query(database, from_json(request))
    return run(connection, database, is_safe_alias, q, mode)
