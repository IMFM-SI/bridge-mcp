"""Decode a query from its JSON form into the input AST.

The JSON shape used over the MCP interface:
`{"domains": [[v, d], ...], "output": {name: "e", ...}, "condition": "...",
  "order": [["e", "asc"], ...], "limit": n}`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bridge_mcp.mathql import input as input_ast
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import Direction
from bridge_mcp.mathql.parser import parse_expression, parse_identifier


def _expression(value: Any) -> input_ast.Expr:
    if isinstance(value, str):
        return parse_expression(value)
    else:
        raise MathQLError("an expression must be a string")


def _binding(pair: Any) -> input_ast.Binding:
    match pair:
        case [var, domain]:
            return input_ast.Binding(parse_identifier(str(var)), parse_identifier(str(domain)))
        case _:
            raise MathQLError("a domain binding must be a [variable, domain] pair")


def _output_column(name: Any, value: Any) -> tuple[str, input_ast.Expr]:
    return parse_identifier(str(name)), _expression(value)


def _output(data: Any) -> tuple[tuple[str, input_ast.Expr], ...]:
    if isinstance(data, Mapping):
        return tuple(_output_column(name, value) for name, value in data.items())
    else:
        raise MathQLError("'output' must map column names to expression strings")


def _direction(text: Any) -> Direction:
    match str(text):
        case "asc":
            return Direction.ASC
        case "desc":
            return Direction.DESC
        case other:
            raise MathQLError(f'order direction must be "asc" or "desc", got "{other}"')


def _order_entry(pair: Any) -> input_ast.OrderEntry:
    match pair:
        case [expression, direction]:
            return input_ast.OrderEntry(_expression(expression), _direction(direction))
        case _:
            raise MathQLError("an order entry must be an [expression, direction] pair")


def _limit(value: Any) -> int | None:
    match value:
        case None:
            return None
        case bool():
            raise MathQLError("'limit' must be a non-negative integer")
        case int() as n if n >= 0:
            return n
        case _:
            raise MathQLError("'limit' must be a non-negative integer")


def from_json(data: Mapping[str, Any]) -> input_ast.Query:
    """Decode a query from its JSON object."""
    if "domains" not in data or "output" not in data:
        raise MathQLError("a query must have 'domains' and 'output'")
    domains = tuple(_binding(pair) for pair in data["domains"])
    output = _output(data["output"])
    condition = _expression(data["condition"]) if data.get("condition") is not None else None
    order = (
        tuple(_order_entry(entry) for entry in data["order"])
        if data.get("order") is not None
        else None
    )
    return input_ast.Query(domains, output, condition, order, _limit(data.get("limit")))
