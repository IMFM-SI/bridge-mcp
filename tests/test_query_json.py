"""Checks for decoding a query from its JSON form."""

import pytest

from bridge_mcp.mathql import input as ast
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import ComparisonOp, Direction
from bridge_mcp.mathql.query_json import from_json


def test_minimal() -> None:
    q = from_json({"domains": [["g", "Graph8"]], "output": ["g.graph6"]})
    assert q.domains == (ast.Binding("g", "Graph8"),)
    assert q.output == (ast.OutputItem("g", "graph6"),)
    assert q.condition is None
    assert q.order is None
    assert q.limit is None


def test_full() -> None:
    q = from_json(
        {
            "domains": [["g", "Graph8"]],
            "output": ["g.graph6", "g"],
            "condition": "g.num_vertices == 5",
            "order": [["g.num_edges", "desc"]],
            "limit": 3,
        }
    )
    assert q.output == (ast.OutputItem("g", "graph6"), ast.OutputItem("g", None))
    assert q.condition == ast.Compare(
        ComparisonOp.EQ, ast.Field("g", "num_vertices"), ast.IntLit(5)
    )
    assert q.order == (ast.OrderEntry(ast.Field("g", "num_edges"), Direction.DESC),)
    assert q.limit == 3


def test_errors() -> None:
    with pytest.raises(MathQLError):
        from_json({"output": ["g"]})  # missing domains
    with pytest.raises(MathQLError):
        from_json({"domains": [["g"]], "output": ["g"]})  # malformed binding
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "Graph8"]], "output": ["g"], "order": [["g.n", "up"]]})
