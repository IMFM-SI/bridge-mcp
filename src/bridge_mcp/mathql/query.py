"""The typed query: the result of type-checking a query."""

from __future__ import annotations

from dataclasses import dataclass

from bridge_mcp.mathql import expr
from bridge_mcp.mathql.operators import Direction


@dataclass(frozen=True)
class Binding:
    """A bound variable and the name of the domain it ranges over."""

    var: str
    domain: str


@dataclass(frozen=True)
class OutputItem:
    """A variable `x` (whole object, `label` is None) or a field projection `x.label`."""

    var: str
    label: str | None


@dataclass(frozen=True)
class OrderEntry:
    key: expr.Expr
    direction: Direction


@dataclass(frozen=True)
class Query:
    variables: tuple[Binding, ...]
    output: tuple[OutputItem, ...]
    condition: expr.Expr
    order: tuple[OrderEntry, ...]
    limit: int | None
