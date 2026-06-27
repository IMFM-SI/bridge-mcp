"""The input syntax: the untyped output of the parser, before type-checking."""

from __future__ import annotations

from dataclasses import dataclass

from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, Direction, UnaryOp


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
class Proj:
    expr: Expr
    index: int


@dataclass(frozen=True)
class ListExpr:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class TupleExpr:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class Ite:
    cond: Expr
    then_: Expr
    else_: Expr


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
    left: Expr
    right: Expr


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
    | Proj
    | ListExpr
    | TupleExpr
    | Ite
    | UnOp
    | BinOp
    | Compare
    | Defined
    | Undefined
)


@dataclass(frozen=True)
class OutputItem:
    """A domain variable `x` (the whole object), or a field projection `x.label`."""

    var: str
    field: str | None = None


@dataclass(frozen=True)
class Binding:
    """A domain binding `x in D`: the variable and the domain it ranges over."""

    var: str
    domain: str


@dataclass(frozen=True)
class OrderEntry:
    expr: Expr
    direction: Direction


@dataclass(frozen=True)
class Query:
    """A query. `condition`, `order`, and `limit` are optional in the input; the
    type-checker fills in `true`, the empty list, and none respectively."""

    domains: tuple[Binding, ...]
    output: tuple[OutputItem, ...]
    condition: Expr | None = None
    order: tuple[OrderEntry, ...] | None = None
    limit: int | None = None
