"""The input syntax: the untyped output of the parser, before type-checking.

Each expression node carries an optional source `span`, set by the parser and excluded
from equality, so type errors can point at the offending sub-expression.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, Direction, UnaryOp


@dataclass(frozen=True)
class Span:
    """A source location: 1-based line and column, 0-based character offsets."""

    line: int
    column: int
    start: int
    end: int


@dataclass(frozen=True)
class IntLit:
    value: int
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class BoolLit:
    value: bool
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class StrLit:
    value: str
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Ident:
    name: str
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Id:
    """The primary key of the object denoted by `expr`."""

    expr: Expr
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Obj:
    """The object of `domain` with the given primary key, `D[e1, ..., en]`."""

    domain: str
    args: tuple[Expr, ...]
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Call:
    """A function applied to arguments, `f(e1, ..., en)`."""

    name: str
    args: tuple[Expr, ...]
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Field:
    expr: Expr
    label: str
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Proj:
    expr: Expr
    index: int
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class ListExpr:
    items: tuple[Expr, ...]
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class TupleExpr:
    items: tuple[Expr, ...]
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Ite:
    cond: Expr
    then_: Expr
    else_: Expr
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class UnOp:
    op: UnaryOp
    expr: Expr
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class BinOp:
    op: BinaryOp
    left: Expr
    right: Expr
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Compare:
    op: ComparisonOp
    left: Expr
    right: Expr
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Defined:
    expr: Expr
    span: Span | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Undefined:
    expr: Expr
    span: Span | None = field(default=None, compare=False)


Expr = (
    IntLit
    | BoolLit
    | StrLit
    | Ident
    | Id
    | Obj
    | Call
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
    type-checker fills in `true`, the empty list, and none respectively. `postprocess`
    defaults to the empty stage."""

    domains: tuple[Binding, ...]
    output: tuple[tuple[str, Expr], ...]
    condition: Expr | None = None
    order: tuple[OrderEntry, ...] | None = None
    limit: int | None = None
    postprocess: tuple[tuple[str, Expr], ...] = ()
