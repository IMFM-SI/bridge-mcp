"""The typed syntax: the output of type-checking."""

from __future__ import annotations

from dataclasses import dataclass

from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, UnaryOp
from bridge_mcp.mathql.types import Ty


@dataclass(frozen=True)
class IntLit:
    value: int


@dataclass(frozen=True)
class BoolLit:
    value: bool


@dataclass(frozen=True)
class StrLit:
    value: str


@dataclass(frozen=True)
class Const:
    name: str


@dataclass(frozen=True)
class Field:
    var: str
    label: str


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
    ty: Ty
    left: Expr
    right: Expr


@dataclass(frozen=True)
class ListExpr:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class TupleExpr:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class Proj:
    expr: Expr
    index: int


@dataclass(frozen=True)
class Ite:
    cond: Expr
    then_: Expr
    else_: Expr


@dataclass(frozen=True)
class Defined:
    expr: Expr


@dataclass(frozen=True)
class Undefined:
    expr: Expr


Expr = (
    IntLit
    | BoolLit
    | StrLit
    | Const
    | Field
    | UnOp
    | BinOp
    | Compare
    | ListExpr
    | TupleExpr
    | Proj
    | Ite
    | Defined
    | Undefined
)
