"""Decode a query from its JSON form into the input AST.

The JSON shape used over the MCP interface:
`{"domains": [[v, d], ...], "output": ["x.l", ...], "condition": "...",
  "order": [["e", "asc"], ...], "limit": n}`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bridge_mcp.mathql import input as input_ast
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import Direction
from bridge_mcp.mathql.parser import parse_expression


def _binding(pair: Any) -> input_ast.Binding:
    match pair:
        case [var, domain]:
            return input_ast.Binding(str(var), str(domain))
        case _:
            raise MathQLError("a domain binding must be a [variable, domain] pair")


def _output_item(text: Any) -> input_ast.OutputItem:
    var, _, label = str(text).partition(".")
    return input_ast.OutputItem(var, label or None)


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
            return input_ast.OrderEntry(
                parse_expression(str(expression)), _direction(direction)
            )
        case _:
            raise MathQLError("an order entry must be an [expression, direction] pair")


def from_json(data: Mapping[str, Any]) -> input_ast.Query:
    """Decode a query from its JSON object."""
    if "domains" not in data or "output" not in data:
        raise MathQLError("a query must have 'domains' and 'output'")
    domains = tuple(_binding(pair) for pair in data["domains"])
    output = tuple(_output_item(item) for item in data["output"])
    condition = (
        parse_expression(data["condition"]) if data.get("condition") is not None else None
    )
    order = (
        tuple(_order_entry(entry) for entry in data["order"])
        if data.get("order") is not None
        else None
    )
    limit = data.get("limit")
    return input_ast.Query(domains, output, condition, order, limit)
