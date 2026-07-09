"""The typed query: the result of type-checking a query."""

from __future__ import annotations

from dataclasses import dataclass

from bridge_mcp.mathql import expr
from bridge_mcp.mathql.operators import Direction
from bridge_mcp.mathql.types import Ty


@dataclass(frozen=True)
class Binding:
    """A bound variable and the name of the domain it ranges over."""

    var: str
    domain: str


@dataclass(frozen=True)
class OutputColumn:
    """A result column: its name, its type, and the expression it returns."""

    name: str
    ty: Ty
    expr: expr.Expr


@dataclass(frozen=True)
class OrderEntry:
    key: expr.Expr
    direction: Direction


@dataclass(frozen=True)
class Query:
    variables: tuple[Binding, ...]
    output: tuple[OutputColumn, ...]
    condition: expr.Expr
    order: tuple[OrderEntry, ...]
    limit: int | None
