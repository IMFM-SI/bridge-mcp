"""Bidirectional type-checking: elaborate the input AST into the typed AST.

`infer` synthesizes a type, `check` checks against an expected one; `infer_domain`
elaborates an object-denoting expression; `check_query` type-checks a whole query.
Ill-typed input raises `MathQLError`, located by the offending node's source span.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Sequence
from typing import TypeVar, assert_never

from bridge_mcp.mathql import expr, query
from bridge_mcp.mathql import input as input_ast
from bridge_mcp.mathql.context import Context
from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.types import (
    BoolType,
    IntType,
    ListType,
    ProductType,
    StringType,
    Ty,
    binary_type,
    product_of,
    render,
    unary_type,
)

_T = TypeVar("_T")


def _error(message: str, node: input_ast.Expr) -> MathQLError:
    if node.span is None:
        return MathQLError(message)
    else:
        return MathQLError(f"{message} (line {node.span.line}, column {node.span.column})")


def _at(node: input_ast.Expr, lookup: Callable[[], _T]) -> _T:
    """Run a context lookup, locating any error at `node`."""
    try:
        return lookup()
    except MathQLError as error:
        raise _error(str(error), node) from None


def infer(ctx: Context, e: input_ast.Expr) -> tuple[Ty, expr.Expr]:
    """Infer the type of `e` and elaborate it to a typed expression."""
    match e:
        case input_ast.IntLit(value):
            return IntType(), expr.IntLit(value)
        case input_ast.BoolLit(value):
            return BoolType(), expr.BoolLit(value)
        case input_ast.StrLit(value):
            return StringType(), expr.StrLit(value)
        case input_ast.Ident(name):
            return _at(e, lambda: ctx.get_ident(name)), expr.Ident(name)
        case input_ast.Id(operand):
            domain, typed_domain = infer_domain(ctx, operand)
            return (
                product_of(_at(e, lambda: ctx.get_id_types(domain))),
                expr.Id(typed_domain),
            )
        case input_ast.Obj():
            raise _error("a bare object cannot appear in an expression", e)
        case input_ast.Call(name, args):
            signature = _at(e, lambda: ctx.get_function(name))
            return signature.result_ty, expr.Call(
                name, _check_tuple(ctx, e, args, signature.arg_types)
            )
        case input_ast.Field(operand, label):
            domain, typed_domain = infer_domain(ctx, operand)
            ty = _at(e, lambda: ctx.get_input_field_ty(domain, label))
            return ty, expr.Field(typed_domain, label)
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
                raise _error("cannot infer the type of this empty list", e)
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


def infer_domain(ctx: Context, e: input_ast.Expr) -> tuple[str, expr.Domain]:
    """Infer the domain of an object-denoting expression, elaborating it."""
    match e:
        case input_ast.Ident(name):
            return _at(e, lambda: ctx.get_domain_ident(name)), expr.DomainIdent(name)
        case input_ast.Obj(domain, args):
            id_types = _at(e, lambda: ctx.get_id_types(domain))
            return domain, expr.Obj(domain, _check_tuple(ctx, e, args, id_types))
        case input_ast.Field(operand, label):
            head, typed = infer_domain(ctx, operand)
            linked = _at(e, lambda: ctx.get_domain_field(head, label))
            return linked, expr.DomainField(typed, label)
        case _:
            raise _error("invalid expression in a field projection", e)


def _check_tuple(
    ctx: Context,
    node: input_ast.Expr,
    items: tuple[input_ast.Expr, ...],
    factors: tuple[Ty, ...],
) -> tuple[expr.Expr, ...]:
    """Check a tuple's components against the product's component types."""
    if len(items) != len(factors):
        raise _error("tuple has the wrong number of components", node)
    else:
        return tuple(check(ctx, item, ty) for item, ty in zip(items, factors, strict=True))


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
                    return expr.TupleExpr(_check_tuple(ctx, e, items, factors))
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
    """Check the domain bindings. The variables are distinct."""
    for position, binding in enumerate(domains):
        if binding.domain not in ctx.domains:
            raise MathQLError(f"unknown domain {binding.domain}")
        if any(earlier.var == binding.var for earlier in domains[:position]):
            raise MathQLError(f"duplicate domain variable {binding.var}")
    extended = functools.reduce(
        lambda c, b: c.extend_domain_ident(b.var, b.domain), domains, ctx
    )
    return extended, tuple(query.Binding(b.var, b.domain) for b in domains)


def _check_output(
    ctx: Context, entries: Sequence[tuple[str, input_ast.Expr]]
) -> tuple[query.OutputColumn, ...]:
    """Check each output column in `ctx`, the context of the domain variables. The column
    names are distinct from one another."""
    match entries:
        case []:
            return ()
        case [(name, e), *rest]:
            checked = _check_output(ctx, rest)
            if any(column.name == name for column in checked):
                raise _error(f"duplicate output column {name}", e)
            ty, typed = infer(ctx, e)
            return (query.OutputColumn(name, ty, typed), *checked)
    raise AssertionError("unreachable")


def _order_entry(ctx: Context, entry: input_ast.OrderEntry) -> query.OrderEntry:
    _, typed = infer(ctx, entry.expr)
    return query.OrderEntry(typed, entry.direction)


def _extend_output(ctx: Context, output: tuple[query.OutputColumn, ...]) -> Context:
    """Bring the output columns into scope, each at its inferred type."""
    return functools.reduce(lambda c, o: c.extend_ident(o.name, o.ty), output, ctx)


def _check_postprocess(
    ctx: Context, entries: Sequence[tuple[str, input_ast.Expr]]
) -> tuple[query.OutputColumn, ...]:
    """Check the postprocess entries in order, each in scope of the output columns and of
    the entries preceding it. A name already in scope is a duplicate."""
    match entries:
        case []:
            return ()
        case [(name, e), *rest]:
            if name in ctx.idents:
                raise _error(f"duplicate field {name} in postprocess", e)
            ty, typed = infer(ctx, e)
            return (
                query.OutputColumn(name, ty, typed),
                *_check_postprocess(ctx.extend_ident(name, ty), rest),
            )
    raise AssertionError("unreachable")


def check_query(database: Database, source: input_ast.Query) -> query.Query:
    """Type-check a query, elaborating it into the typed query.

    The output columns are checked in the context of the domain variables, the order keys
    with the output aliases in scope, and the postprocess entries in the postprocess
    context extended by the output columns.
    """
    ctx, bindings = _check_domains(database.sql_context(), source.domains)
    condition_source = (
        source.condition if source.condition is not None else input_ast.BoolLit(True)
    )
    condition = check(ctx, condition_source, BoolType())
    output = _check_output(ctx, source.output)
    order = tuple(
        _order_entry(_extend_output(ctx, output), entry) for entry in source.order or ()
    )
    postprocess = _check_postprocess(
        _extend_output(database.post_context(), output), source.postprocess
    )
    return query.Query(bindings, output, condition, order, source.limit, postprocess)
