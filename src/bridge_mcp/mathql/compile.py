"""Compilation of a type-checked query to SQL: scalar expressions compile to SQL
expressions, and domain expressions compile to aliased table rows, hoisted into shared
LEFT JOINs."""

from __future__ import annotations

import functools
import itertools
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, assert_never

from bridge_mcp.mathql import expr, sql
from bridge_mcp.mathql.database import Column, Database, Schema
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import BinaryOp
from bridge_mcp.mathql.query import Binding, Query
from bridge_mcp.mathql.types import ListType, ProductType

Mode = Literal["sound", "complete"]
"""Which rows a condition that is NULL on them, neither true nor false, keeps: none when
sound, so that each row returned matches; all of them when complete, so that no row that
might match is missing, each row then carrying whether it matches for certain."""


@dataclass(frozen=True)
class DomainEntry:
    """A domain variable's entry: the domain it ranges over."""

    domain: str


@dataclass(frozen=True)
class ConstEntry:
    """A constant's or output alias's entry: the SQL expression it stands for."""

    expr: sql.Expr


ContextEntry = DomainEntry | ConstEntry


@dataclass(frozen=True)
class SqlContext:
    """The resolution context of a compilation: the entry of each identifier, the schema
    of each domain, the SQL function each MathQL function compiles to and the cost of a
    call to it, and whether a name is free of the column names of the database, and so
    usable as an alias."""

    idents: Mapping[str, ContextEntry]
    schemas: Mapping[str, Schema]
    functions: Mapping[str, str]
    costs: Mapping[str, int]
    is_safe_alias: Callable[[str], bool]

    def get_function(self, name: str) -> str:
        match self.functions.get(name):
            case None:
                raise MathQLError(f"unknown function {name}")
            case sql_name:
                return sql_name

    def get_schema(self, domain: str) -> Schema:
        match self.schemas.get(domain):
            case None:
                raise MathQLError(f"unknown domain name {domain}")
            case schema:
                return schema

    def get_column(self, domain: str, label: str) -> Column:
        match self.get_schema(domain).columns.get(label):
            case None:
                raise MathQLError(f"unknown column {label} in schema {domain}")
            case column:
                return column


@dataclass
class CompileState:
    """The state of a compilation: the next alias to try, the alias of each domain
    variable, the hoisted joins, and the mapping from hoisted domain expressions to their
    alias and domain."""

    next_alias: int
    var_alias: dict[str, str]
    joins: list[sql.Join]
    hoisted: dict[expr.Domain, tuple[str, str]]


_ALIAS_FUEL = 1000


def _fresh_safe_alias(ctx: SqlContext, state: CompileState) -> str:
    """The first of `c{n}`, `c{n+1}`, … that `ctx.is_safe_alias` accepts, counting from
    the state's next alias, which then moves past it."""
    indices = itertools.islice(itertools.count(state.next_alias), _ALIAS_FUEL)
    for index in indices:
        if ctx.is_safe_alias(f"c{index}"):
            state.next_alias = index + 1
            return f"c{index}"
    raise MathQLError("internal error: no safe alias available")


def _add_join(
    ctx: SqlContext,
    state: CompileState,
    table: str,
    equalities: tuple[tuple[str, sql.Expr], ...],
) -> str:
    """Hoist a `LEFT JOIN` of `table` under a fresh alias, which is returned."""
    alias = _fresh_safe_alias(ctx, state)
    state.joins.append(sql.Join(table, alias, equalities))
    return alias


def compile_domain(ctx: SqlContext, state: CompileState, d: expr.Domain) -> tuple[str, str]:
    """The alias of the row denoted by a domain expression, and its domain. The result
    for an equal expression is stored and reused. A domain variable resolves to the alias
    allocated for its binding; an `Obj` or a domain-valued field is hoisted to a join."""
    match d:
        case expr.DomainIdent(name):
            match ctx.idents.get(name):
                case DomainEntry(domain):
                    match state.var_alias.get(name):
                        case None:
                            raise MathQLError(f"unbound domain variable {name}")
                        case alias:
                            return alias, domain
                case ConstEntry():
                    raise MathQLError(f"{name} is not a domain variable")
                case None:
                    raise MathQLError(f"unknown identifier {name}")
        case expr.Obj(domain, args):
            if d in state.hoisted:
                return state.hoisted[d]
            else:
                schema = ctx.get_schema(domain)
                keys = tuple(compile_expr(ctx, state, arg) for arg in args)
                equalities = tuple(zip(schema.primary_columns(), keys, strict=True))
                alias = _add_join(ctx, state, schema.table, equalities)
                state.hoisted[d] = (alias, domain)
                return alias, domain
        case expr.DomainField(head, label):
            if d in state.hoisted:
                return state.hoisted[d]
            else:
                head_alias, head_domain = compile_domain(ctx, state, head)
                foreign = ctx.get_schema(head_domain).get_foreign_key(label)
                table = ctx.get_schema(foreign.domain).table
                equalities = tuple(
                    (there, sql.Col(head_alias, here)) for here, there in foreign.columns
                )
                alias = _add_join(ctx, state, table, equalities)
                state.hoisted[d] = (alias, foreign.domain)
                return alias, foreign.domain
    assert_never(d)


def _row_presence(
    ctx: SqlContext, state: CompileState, domain: expr.Domain, negated: bool
) -> sql.Expr:
    """The row-presence test behind `Defined`/`Undefined` of an object's id: NULL-ness
    of the first primary-key column, or true for an empty key."""
    alias, name = compile_domain(ctx, state, domain)
    columns = ctx.get_schema(name).primary_columns()
    if columns == ():
        return sql.BoolLit(True)
    else:
        column = sql.Col(alias, columns[0])
        return sql.IsNull(column) if negated else sql.IsNotNull(column)


def _cost(ctx: SqlContext, e: expr.Expr) -> int:
    """The sum of the costs of the function calls in `e`, outside its domain
    expressions."""
    match e:
        case expr.Call(name, args):
            return ctx.costs.get(name, 0) + sum(_cost(ctx, arg) for arg in args)
        case expr.UnOp(_, operand) | expr.Proj(operand, _):
            return _cost(ctx, operand)
        case expr.Defined(operand) | expr.Undefined(operand):
            return _cost(ctx, operand)
        case expr.BinOp(_, left, right) | expr.Compare(_, _, left, right):
            return _cost(ctx, left) + _cost(ctx, right)
        case expr.Ite(cond, then_, else_):
            return _cost(ctx, cond) + _cost(ctx, then_) + _cost(ctx, else_)
        case expr.TupleExpr(items) | expr.ListExpr(items):
            return sum(_cost(ctx, item) for item in items)
        case _:
            return 0


def _operands(op: BinaryOp, e: expr.Expr) -> list[expr.Expr]:
    """The operands of the chain of `op` that `e` heads: `a && (b && c)` has `a`, `b`
    and `c`."""
    match e:
        case expr.BinOp(head, left, right) if head == op:
            return _operands(op, left) + _operands(op, right)
        case _:
            return [e]


def _cheapest_first(
    ctx: SqlContext, state: CompileState, op: BinaryOp, e: expr.Expr
) -> sql.Expr:
    """The chain of `&&` or `||` that `e` heads, its operands ordered by cost, the
    written order kept among equal costs. SQLite evaluates a condition's operands in
    order and stops at the first that decides it, so an expensive call runs on fewer
    rows. The order does not change the value: both operators are commutative, absent
    values included, and no operand fails."""
    operands = sorted(_operands(op, e), key=lambda operand: _cost(ctx, operand))
    compiled = [compile_expr(ctx, state, operand) for operand in operands]
    return functools.reduce(lambda left, right: sql.BinOp(op, left, right), compiled)


def compile_expr(ctx: SqlContext, state: CompileState, e: expr.Expr) -> sql.Expr:
    """Compile a typed expression to a SQL expression."""
    match e:
        case expr.IntLit(value):
            return sql.IntLit(value)
        case expr.BoolLit(value):
            return sql.BoolLit(value)
        case expr.StrLit(value):
            return sql.StrLit(value)
        case expr.Ident(name):
            match ctx.idents.get(name):
                case ConstEntry(constant):
                    return constant
                case DomainEntry():
                    raise MathQLError(f"{name} is a domain variable, not a value")
                case None:
                    raise MathQLError(f"unknown constant {name}")
        case expr.Id(domain):
            alias, name = compile_domain(ctx, state, domain)
            columns = ctx.get_schema(name).primary_columns()
            return sql.json_array(tuple(sql.Col(alias, column) for column in columns))
        case expr.Field(domain, label):
            alias, name = compile_domain(ctx, state, domain)
            return sql.Col(alias, ctx.get_column(name, label).column)
        case expr.Call(name, args):
            compiled = tuple(compile_expr(ctx, state, arg) for arg in args)
            return sql.Call(ctx.get_function(name), compiled)
        case expr.UnOp(op, operand):
            return sql.UnOp(op, compile_expr(ctx, state, operand))
        case expr.BinOp(BinaryOp.AND | BinaryOp.OR as op, _, _):
            return _cheapest_first(ctx, state, op, e)
        case expr.BinOp(op, left, right):
            return sql.BinOp(
                op, compile_expr(ctx, state, left), compile_expr(ctx, state, right)
            )
        case expr.Compare(op, ty, left, right):
            left_sql = compile_expr(ctx, state, left)
            right_sql = compile_expr(ctx, state, right)
            match ty:
                case ListType() | ProductType():
                    return sql.Compare(op, sql.Json(left_sql), sql.Json(right_sql))
                case _:
                    return sql.Compare(op, left_sql, right_sql)
        case expr.Ite(cond, then_, else_):
            return sql.Case(
                compile_expr(ctx, state, cond),
                compile_expr(ctx, state, then_),
                compile_expr(ctx, state, else_),
            )
        case expr.Defined(operand):
            match operand:
                case expr.Id(domain):
                    return _row_presence(ctx, state, domain, negated=False)
                case _:
                    return sql.IsNotNull(compile_expr(ctx, state, operand))
        case expr.Undefined(operand):
            match operand:
                case expr.Id(domain):
                    return _row_presence(ctx, state, domain, negated=True)
                case _:
                    return sql.IsNull(compile_expr(ctx, state, operand))
        case expr.TupleExpr(items):
            return sql.JsonArray(tuple(compile_expr(ctx, state, item) for item in items))
        case expr.ListExpr(items):
            return sql.JsonArray(tuple(compile_expr(ctx, state, item) for item in items))
        case expr.Proj(operand, index):
            return sql.JsonExtract(compile_expr(ctx, state, operand), index)
    assert_never(e)


def _bind_variable(
    ctx: SqlContext, state: CompileState, database: Database, binding: Binding
) -> tuple[str, str]:
    """The table of a domain binding under a fresh alias, which is recorded as the
    variable's."""
    match database.domains.get(binding.domain):
        case None:
            raise MathQLError(f"unknown domain {binding.domain}")
        case schema:
            alias = _fresh_safe_alias(ctx, state)
            state.var_alias[binding.var] = alias
            return schema.table, alias


def compile_query(
    database: Database,
    is_safe_alias: Callable[[str], bool],
    q: Query,
    mode: Mode = "sound",
) -> sql.Query:
    """Compile a type-checked query to a SQL query, with `is_safe_alias` deciding which
    names may serve as aliases. In complete mode the condition admits a row on which it
    is NULL, and a last output column says whether it is true there."""
    idents: dict[str, ContextEntry] = {
        **{c.name: ConstEntry(c.sql) for c in database.constants},
        **{b.var: DomainEntry(b.domain) for b in q.variables},
    }
    functions = {f.name: f.sql_name for f in database.sql_functions}
    costs = {f.name: f.cost for f in database.sql_functions}
    ctx = SqlContext(
        idents=idents,
        schemas=database.domains,
        functions=functions,
        costs=costs,
        is_safe_alias=is_safe_alias,
    )
    state = CompileState(next_alias=1, var_alias={}, joins=[], hoisted={})
    froms = tuple(_bind_variable(ctx, state, database, b) for b in q.variables)
    columns = tuple(
        (o.name, _fresh_safe_alias(ctx, state), compile_expr(ctx, state, o.expr))
        for o in q.output
    )
    output = tuple((e, alias) for _, alias, e in columns)
    aliased = SqlContext(
        idents={**idents, **{name: ConstEntry(sql.Ref(a)) for name, a, _ in columns}},
        schemas=database.domains,
        functions=functions,
        costs=costs,
        is_safe_alias=is_safe_alias,
    )
    cond = compile_expr(ctx, state, q.condition)
    keys = ((compile_expr(aliased, state, entry.key), entry.direction) for entry in q.order)
    order = tuple((e, direction) for e, direction in keys if not sql.is_constant(e))
    match mode:
        case "sound":
            admitted = cond
        case "complete":
            output = (*output, (sql.IsTrue(cond), _fresh_safe_alias(ctx, state)))
            admitted = sql.IsNotFalse(cond)
    return sql.Query(
        froms=froms,
        joins=tuple(state.joins),
        output=output,
        cond=admitted,
        order=order,
        limit=q.limit,
    )
