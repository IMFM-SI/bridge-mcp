"""Compilation of a type-checked query to SQL: scalar expressions compile to SQL
expressions, and domain expressions compile to aliased table rows, hoisted into shared
LEFT JOINs."""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from typing import assert_never

from bridge_mcp.mathql import expr, sql
from bridge_mcp.mathql.database import Column, Database, Schema
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.query import Query
from bridge_mcp.mathql.types import ListType, ProductType


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
    of each domain, and the SQL function each MathQL function compiles to."""

    idents: Mapping[str, ContextEntry]
    schemas: Mapping[str, Schema]
    functions: Mapping[str, str]

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
    """The state of a compilation: the aliases in use, the hoisted joins, and the
    mapping from hoisted domain expressions to their alias and domain."""

    taken: list[str]
    joins: list[sql.Join]
    hoisted: dict[expr.Domain, tuple[str, str]]


def _first_free(taken: list[str], stem: str) -> str:
    """`stem`, or the first `stemk` (k >= 2) not in `taken`, case-insensitively."""
    lowered = {name.lower() for name in taken}
    candidates = (stem if i == 0 else f"{stem}{i + 1}" for i in itertools.count())
    return next(name for name in candidates if name.lower() not in lowered)


def _fresh_alias(state: CompileState, stem: str) -> str:
    """A fresh alias formed from `stem`, recorded as taken."""
    name = _first_free(state.taken, stem)
    state.taken.append(name)
    return name


def _domain_stem(d: expr.Domain) -> str:
    """The stem of the alias of a hoisted domain expression."""
    match d:
        case expr.DomainIdent(name):
            return name
        case expr.Obj(domain, _):
            return domain
        case expr.DomainField(head, label):
            return f"{_domain_stem(head)}_{label}"
    assert_never(d)


def _add_join(
    state: CompileState,
    table: str,
    stem: str,
    equalities: tuple[tuple[str, sql.Expr], ...],
) -> str:
    """Hoist a `LEFT JOIN` of `table` under a fresh alias, which is returned."""
    alias = _fresh_alias(state, stem)
    state.joins.append(sql.Join(table, alias, equalities))
    return alias


def compile_domain(ctx: SqlContext, state: CompileState, d: expr.Domain) -> tuple[str, str]:
    """The alias of the row denoted by a domain expression, and its domain. The result
    for an equal expression is stored and reused. A domain variable is its own alias; an
    `Obj` or a domain-valued field is hoisted to a join."""
    match d:
        case expr.DomainIdent(name):
            match ctx.idents.get(name):
                case DomainEntry(domain):
                    return name, domain
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
                alias = _add_join(state, schema.table, _domain_stem(d), equalities)
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
                alias = _add_join(state, table, _domain_stem(d), equalities)
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


def compile_query(database: Database, q: Query) -> sql.Query:
    """Compile a type-checked query to a SQL query. The order keys compile with each
    output alias bound to a bare-name reference, which SQLite resolves in ORDER BY."""
    for binding in q.variables:
        if binding.domain not in database.domains:
            raise MathQLError(f"unknown domain {binding.domain}")
    froms = tuple((database.domains[b.domain].table, b.var) for b in q.variables)
    idents: dict[str, ContextEntry] = {
        **{c.name: ConstEntry(c.sql) for c in database.constants},
        **{b.var: DomainEntry(b.domain) for b in q.variables},
    }
    functions = {f.name: f.sql_name for f in database.sql_functions}
    ctx = SqlContext(idents=idents, schemas=database.domains, functions=functions)
    aliased = SqlContext(
        idents={**idents, **{o.name: ConstEntry(sql.Ref(o.name)) for o in q.output}},
        schemas=database.domains,
        functions=functions,
    )
    state = CompileState(taken=[b.var for b in q.variables], joins=[], hoisted={})
    output = tuple((compile_expr(ctx, state, o.expr), o.name) for o in q.output)
    cond = compile_expr(ctx, state, q.condition)
    order = tuple(
        (compile_expr(aliased, state, entry.key), entry.direction) for entry in q.order
    )
    return sql.Query(
        froms=froms,
        joins=tuple(state.joins),
        output=output,
        cond=cond,
        order=order,
        limit=q.limit,
    )
