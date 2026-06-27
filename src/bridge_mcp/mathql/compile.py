"""Compile a typed expression to the SQL expression AST (SQLite)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import assert_never

from bridge_mcp.mathql import expr, sql
from bridge_mcp.mathql.errors import MathQLError


@dataclass(frozen=True)
class SqlContext:
    """Resolves each bound variable's field to a column, and each constant to SQL.

    A field `x.label` compiles to the column `columns[(x, label)]` on the table aliased by
    the variable `x`.
    """

    columns: Mapping[tuple[str, str], str]
    constants: Mapping[str, sql.Expr]


def compile_expr(ctx: SqlContext, e: expr.Expr) -> sql.Expr:
    """Compile a typed expression to a SQL expression."""
    match e:
        case expr.IntLit(value):
            return sql.IntLit(value)
        case expr.BoolLit(value):
            return sql.BoolLit(value)
        case expr.StrLit(value):
            return sql.StrLit(value)
        case expr.Const(name):
            constant = ctx.constants.get(name)
            if constant is None:
                raise MathQLError(f"no SQL for constant {name}")
            return constant
        case expr.Field(var, label):
            column = ctx.columns.get((var, label))
            if column is None:
                raise MathQLError(f"no column for {var}.{label}")
            return sql.Col(var, column)
        case expr.UnOp(op, operand):
            return sql.UnOp(op, compile_expr(ctx, operand))
        case expr.BinOp(op, left, right):
            return sql.BinOp(op, compile_expr(ctx, left), compile_expr(ctx, right))
        case expr.Compare(op, _, left, right):
            return sql.Compare(op, compile_expr(ctx, left), compile_expr(ctx, right))
        case expr.Ite(cond, then_, else_):
            return sql.Case(
                compile_expr(ctx, cond), compile_expr(ctx, then_), compile_expr(ctx, else_)
            )
        case expr.Defined(operand):
            return sql.IsNotNull(compile_expr(ctx, operand))
        case expr.Undefined(operand):
            return sql.IsNull(compile_expr(ctx, operand))
        case expr.TupleExpr(items):
            return sql.JsonArray(tuple(compile_expr(ctx, item) for item in items))
        case expr.Proj(obj, index):
            return sql.JsonExtract(compile_expr(ctx, obj), index)
        case expr.ListExpr(items):
            return sql.JsonArray(tuple(compile_expr(ctx, item) for item in items))
    assert_never(e)
