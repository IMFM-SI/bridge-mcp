"""Checks for decoding a query from its JSON form."""

import pytest

from bridge_mcp.mathql import input as ast
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import ComparisonOp, Direction
from bridge_mcp.mathql.query_json import from_json


def test_minimal() -> None:
    q = from_json({"domains": [["g", "Graph"]], "output": [["graph6", "g.graph6"]]})
    assert q.domains == (ast.Binding("g", "Graph"),)
    assert q.output == (("graph6", ast.Field(ast.Ident("g"), "graph6")),)
    assert q.condition is None
    assert q.order is None
    assert q.limit is None


def test_full() -> None:
    q = from_json(
        {
            "domains": [["g", "Graph"]],
            "output": [["g6", "id(g)"], ["edges", "g.num_edges"]],
            "condition": "g.num_vertices == 5",
            "order": [["g.num_edges", "desc"]],
            "limit": 3,
        }
    )
    assert q.output == (
        ("g6", ast.Id(ast.Ident("g"))),
        ("edges", ast.Field(ast.Ident("g"), "num_edges")),
    )
    assert q.condition == ast.Compare(
        ComparisonOp.EQ, ast.Field(ast.Ident("g"), "num_vertices"), ast.IntLit(5)
    )
    assert q.order == (ast.OrderEntry(ast.Field(ast.Ident("g"), "num_edges"), Direction.DESC),)
    assert q.limit == 3


def test_output_keeps_its_order() -> None:
    q = from_json(
        {
            "domains": [["g", "Graph"]],
            "output": [[name, "g.num_edges"] for name in ("zeta", "alpha", "mu", "beta")],
        }
    )
    assert [name for name, _ in q.output] == ["zeta", "alpha", "mu", "beta"]


def test_decoding_admits_a_repeated_column_name() -> None:
    """The type-checker is the layer that rejects one."""
    q = from_json(
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "g.num_vertices"], ["n", "g.num_edges"]],
        }
    )
    assert q.output == (
        ("n", ast.Field(ast.Ident("g"), "num_vertices")),
        ("n", ast.Field(ast.Ident("g"), "num_edges")),
    )


def test_errors() -> None:
    with pytest.raises(MathQLError):
        from_json({"output": [["n", "g.n"]]})  # missing domains
    with pytest.raises(MathQLError):
        from_json({"domains": [["g"]], "output": [["n", "g.n"]]})  # malformed binding
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "G"]], "output": {"n": "g.n"}})  # output must be a list
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "G"]], "output": ["g.n"]})  # entry must be a pair
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "G"]], "output": [["n"]]})  # entry must be a pair
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "G"]], "output": [["g.n", "g.n"]]})  # bad column name
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "G"]], "output": [["if", "g.n"]]})  # keyword column name
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "G"]], "output": [["n", 3]]})  # non-string expression
    with pytest.raises(MathQLError):
        from_json(
            {"domains": [["g", "G"]], "output": [["n", "g.n"]], "order": [["g.n", "up"]]}
        )
    with pytest.raises(MathQLError):
        from_json({"domains": [["g", "G"]], "output": [["n", "g.n"]], "limit": -1})


def test_postprocess_decoding() -> None:
    q = from_json(
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "g.num_vertices"]],
            "postprocess": [["k", "plus(n, 1)"], ["m", "k"]],
        }
    )
    assert [name for name, _ in q.postprocess] == ["k", "m"]
    assert q.postprocess[1] == ("m", ast.Ident("k"))


def test_postprocess_defaults_to_the_empty_stage() -> None:
    q = from_json({"domains": [["g", "Graph"]], "output": [["n", "g.num_vertices"]]})
    assert q.postprocess == ()


def test_postprocess_errors() -> None:
    base: dict[str, object] = {
        "domains": [["g", "Graph"]],
        "output": [["n", "g.num_vertices"]],
    }
    with pytest.raises(MathQLError):
        from_json({**base, "postprocess": {"k": "plus(n, 1)"}})  # an object, not a list
    with pytest.raises(MathQLError):
        from_json({**base, "postprocess": None})
    with pytest.raises(MathQLError):
        from_json({**base, "postprocess": [["k"]]})
    with pytest.raises(MathQLError):
        from_json({**base, "postprocess": [["if", "3"]]})
