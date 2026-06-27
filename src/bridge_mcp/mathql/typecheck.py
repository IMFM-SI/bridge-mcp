"""Bidirectional type-checking: elaborate the input AST into the typed AST.

`infer` synthesizes a type, `check` checks against an expected one; `check_query`
type-checks a whole query. Ill-typed input raises `MathQLError`, located by the offending
node's source span.
"""

from __future__ import annotations

from typing import assert_never

from bridge_mcp.mathql import expr, query
from bridge_mcp.mathql import input as input_ast
from bridge_mcp.mathql.context import Context
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.types import (
    BoolType,
    IntType,
    ListType,
    ProductType,
    StringType,
    Ty,
    binary_type,
    render,
    unary_type,
)


def _error(message: str, node: input_ast.Expr) -> MathQLError:
    if node.span is None:
        return MathQLError(message)
    return MathQLError(f"{message} (line {node.span.line}, column {node.span.column})")


def infer(ctx: Context, e: input_ast.Expr) -> tuple[Ty, expr.Expr]:
    """Infer the type of `e` and elaborate it to a typed expression."""
    match e:
        case input_ast.IntLit(value):
            return IntType(), expr.IntLit(value)
        case input_ast.BoolLit(value):
            return BoolType(), expr.BoolLit(value)
        case input_ast.StrLit(value):
            return StringType(), expr.StrLit(value)
        case input_ast.Const(name):
            ty = ctx.lookup_constant(name)
            if ty is None:
                raise _error(f"unbound constant '{name}'", e)
            return ty, expr.Const(name)
        case input_ast.Field(var, label):
            ty = ctx.lookup_input_field(var, label)
            if ty is None:
                raise _error(f"{var} does not have field '{label}'", e)
            return ty, expr.Field(var, label)
        case input_ast.Proj(obj, index):
            obj_ty, typed_obj = infer(ctx, obj)
            match obj_ty:
                case ProductType(factors):
                    if not 0 <= index < len(factors):
                        raise _error(f"projection index {index} out of range", e)
                    return factors[index], expr.Proj(typed_obj, index)
                case _:
                    raise _error("projection of a non-product", e)
        case input_ast.UnOp(op, operand):
            operand_ty, result_ty = unary_type(op)
            return result_ty, expr.UnOp(op, check(ctx, operand, operand_ty))
        case input_ast.BinOp(op, left, right):
            left_ty, right_ty, result_ty = binary_type(op)
            return result_ty, expr.BinOp(
                op, check(ctx, left, left_ty), check(ctx, right, right_ty)
            )
        case input_ast.Compare(op, left, right):
            ty, typed_left = infer(ctx, left)
            return BoolType(), expr.Compare(op, ty, typed_left, check(ctx, right, ty))
        case input_ast.Defined(operand):
            _, typed = infer(ctx, operand)
            return BoolType(), expr.Defined(typed)
        case input_ast.Undefined(operand):
            _, typed = infer(ctx, operand)
            return BoolType(), expr.Undefined(typed)
        case input_ast.ListExpr(items):
            if not items:
                raise _error("cannot infer the type of an empty list", e)
            element_ty, first = infer(ctx, items[0])
            rest = tuple(check(ctx, item, element_ty) for item in items[1:])
            return ListType(element_ty), expr.ListExpr((first, *rest))
        case input_ast.Ite(cond, then_, else_):
            typed_cond = check(ctx, cond, BoolType())
            ty, typed_then = infer(ctx, then_)
            return ty, expr.Ite(typed_cond, typed_then, check(ctx, else_, ty))
        case input_ast.TupleExpr(items):
            inferred = [infer(ctx, item) for item in items]
            factors = tuple(item_ty for item_ty, _ in inferred)
            typed_items = tuple(typed_item for _, typed_item in inferred)
            return ProductType(factors), expr.TupleExpr(typed_items)
    assert_never(e)


def check(ctx: Context, e: input_ast.Expr, ty: Ty) -> expr.Expr:
    """Check that `e` has type `ty`, elaborating it to a typed expression."""
    match e:
        case input_ast.ListExpr(items):
            match ty:
                case ListType(element):
                    return expr.ListExpr(tuple(check(ctx, item, element) for item in items))
                case _:
                    raise _error(f"expected {render(ty)}, but got a list", e)
        case input_ast.TupleExpr(items):
            match ty:
                case ProductType(factors):
                    if len(items) != len(factors):
                        raise _error("tuple has the wrong number of components", e)
                    return expr.TupleExpr(
                        tuple(
                            check(ctx, item, t) for item, t in zip(items, factors, strict=True)
                        )
                    )
                case _:
                    raise _error(f"expected {render(ty)}, but got a tuple", e)
        case input_ast.Ite(cond, then_, else_):
            typed_cond = check(ctx, cond, BoolType())
            return expr.Ite(typed_cond, check(ctx, then_, ty), check(ctx, else_, ty))
        case _:
            inferred_ty, typed = infer(ctx, e)
            if inferred_ty != ty:
                raise _error(
                    f"type mismatch: expected {render(ty)}, but got {render(inferred_ty)}", e
                )
            return typed


def _check_domains(
    ctx: Context, domains: tuple[input_ast.Binding, ...]
) -> tuple[Context, tuple[query.Binding, ...]]:
    for binding in domains:
        if binding.domain not in ctx.domains:
            raise MathQLError(f"unknown domain {binding.domain}")
    additions = {binding.var: ctx.domains[binding.domain] for binding in domains}
    bindings = tuple(query.Binding(binding.var, binding.domain) for binding in domains)
    return ctx.with_variables(additions), bindings


def _check_output_item(ctx: Context, item: input_ast.OutputItem) -> query.OutputItem:
    if item.field is None:
        if ctx.lookup_variable(item.var) is None:
            raise MathQLError(f"unknown variable {item.var}")
        return query.OutputItem(item.var, None)
    else:
        if not ctx.is_output_field(item.var, item.field):
            raise MathQLError(f"{item.var} does not have output field {item.field}")
        return query.OutputItem(item.var, item.field)


def _check_order_entry(ctx: Context, entry: input_ast.OrderEntry) -> query.OrderEntry:
    ty, typed = infer(ctx, entry.expr)
    match ty:
        case IntType() | BoolType() | StringType():
            return query.OrderEntry(typed, entry.direction)
        case _:
            raise MathQLError(f"cannot order by a value of type {render(ty)}")


def check_query(ctx: Context, source: input_ast.Query) -> query.Query:
    """Type-check a query, elaborating its condition and order into typed expressions."""
    ctx, bindings = _check_domains(ctx, source.domains)
    output = tuple(_check_output_item(ctx, item) for item in source.output)
    condition_source = (
        source.condition if source.condition is not None else input_ast.BoolLit(True)
    )
    condition = check(ctx, condition_source, BoolType())
    order_source = source.order if source.order is not None else ()
    order = tuple(_check_order_entry(ctx, entry) for entry in order_source)
    return query.Query(bindings, output, condition, order, source.limit)
