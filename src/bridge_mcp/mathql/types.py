"""Types of the query language, and the typing of operators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from bridge_mcp.mathql.operators import BinaryOp, UnaryOp


@dataclass(frozen=True)
class IntType:
    pass


@dataclass(frozen=True)
class BoolType:
    pass


@dataclass(frozen=True)
class StringType:
    pass


@dataclass(frozen=True)
class ListType:
    element: Ty


@dataclass(frozen=True)
class ProductType:
    factors: tuple[Ty, ...]


Ty = IntType | BoolType | StringType | ListType | ProductType


def render(ty: Ty) -> str:
    """Render a type as a short string, e.g. `int`, `list int`."""
    match ty:
        case IntType():
            return "int"
        case BoolType():
            return "bool"
        case StringType():
            return "string"
        case ListType(element):
            return f"list {render(element)}"
        case ProductType(factors):
            return "prod [" + ", ".join(render(t) for t in factors) + "]"
    assert_never(ty)


def unary_type(op: UnaryOp) -> tuple[Ty, Ty]:
    """The operand and result type of a unary operator."""
    match op:
        case UnaryOp.NOT:
            return (BoolType(), BoolType())
        case UnaryOp.NEG:
            return (IntType(), IntType())
    assert_never(op)


def binary_type(op: BinaryOp) -> tuple[Ty, Ty, Ty]:
    """The left, right, and result type of a binary operator."""
    match op:
        case BinaryOp.AND | BinaryOp.OR:
            return (BoolType(), BoolType(), BoolType())
        case BinaryOp.ADD | BinaryOp.SUB | BinaryOp.MUL:
            return (IntType(), IntType(), IntType())
    assert_never(op)
