"""Checks for the graphs-small database: SQL rendering and the schema description."""

from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import render_query
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query


def _typed(request: dict) -> object:
    return check_query(database.typing_context(), from_json(request))


def test_render_simple() -> None:
    q = _typed(
        {
            "domains": [["g", "Graph8"]],
            "output": ["g.graph6"],
            "condition": "g.num_vertices == 5",
        }
    )
    rendered = render_query(database, q)
    assert rendered.startswith(
        "SELECT g.graph6, g.num_vertices, g.num_edges, g.degree_sequence,"
    )
    assert "FROM graph AS g WHERE (g.num_vertices = 5)" in rendered


def test_render_order_and_limit() -> None:
    q = _typed(
        {
            "domains": [["g", "Graph8"]],
            "output": ["g.graph6"],
            "condition": "g.num_vertices == 5",
            "order": [["g.num_edges", "desc"]],
            "limit": 3,
        }
    )
    rendered = render_query(database, q)
    assert rendered.endswith("WHERE (g.num_vertices = 5) ORDER BY g.num_edges DESC LIMIT 3")


def test_render_list_literal() -> None:
    q = _typed(
        {
            "domains": [["g", "Graph8"]],
            "output": ["g.graph6"],
            "condition": "g.degree_sequence == [2, 2, 2]",
        }
    )
    assert "(g.degree_sequence = json_array(2, 2, 2))" in render_query(database, q)


def test_describe() -> None:
    described = database.describe()
    assert described["overview"].startswith("All non-isomorphic")
    domains = described["domains"]
    assert domains[0]["name"] == "Graph8"
    fields = {f["label"]: f["type"] for f in domains[0]["fields"]}
    assert fields["graph6"] == "string"
    assert fields["degree_sequence"] == "list int"
    assert "graph6" in domains[0]["output"]
