"""The typed syntax: the output of type-checking."""

from __future__ import annotations

from dataclasses import dataclass

from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, UnaryOp
from bridge_mcp.mathql.types import Ty


@dataclass(frozen=True)
class DomainIdent:
    """A domain variable."""

    name: str


@dataclass(frozen=True)
class Obj:
    """The object of `domain` with the given primary key, `D[e1, ..., en]`."""

    domain: str
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class DomainField:
    """A field of an object that links to an object of another domain."""

    domain: Domain
    label: str


Domain = DomainIdent | Obj | DomainField


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
class Ident:
    """A predefined constant, or an output alias in an order key."""

    name: str


@dataclass(frozen=True)
class Id:
    """The primary key of the object denoted by `domain`."""

    domain: Domain


@dataclass(frozen=True)
class Call:
    """A function of the database applied to arguments, `f(e1, ..., en)`."""

    name: str
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class Field:
    """A scalar field of the object denoted by `domain`."""

    domain: Domain
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
    | Ident
    | Id
    | Call
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
