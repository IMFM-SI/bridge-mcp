"""Checks for the math_data database: SQL rendering and the schema description."""

from typing import Any

from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import compiled_sql_query
from tests.aliases import safe_alias

_safe_alias = safe_alias(database)


def _rendered(request: dict[str, Any]) -> str:
    return compiled_sql_query(database, _safe_alias, request)


def test_render_simple() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"]],
            "condition": "g.num_vertices == 5",
        }
    )
    assert rendered == (
        'SELECT c1."graph6" AS c2 FROM "graph" AS c1 WHERE (c1."num_vertices" = 5)'
    )


def test_render_order_and_limit() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"]],
            "condition": "g.num_vertices == 5",
            "order": [["g.num_edges", "desc"]],
            "limit": 3,
        }
    )
    assert rendered.endswith(
        'WHERE (c1."num_vertices" = 5) ORDER BY c1."num_edges" DESC LIMIT 3'
    )


def test_render_list_literal() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"]],
            "condition": "g.degree_sequence == [2, 2, 2]",
        }
    )
    assert '(json(c1."degree_sequence") = json(json_array(2, 2, 2)))' in rendered


def test_id_is_graph6() -> None:
    rendered = _rendered({"domains": [["g", "Graph"]], "output": [["gid", "id(g)"]]})
    assert rendered == 'SELECT c1."graph6" AS c2 FROM "graph" AS c1 WHERE 1'


def test_describe() -> None:
    described: Any = database.describe()
    assert described["overview"].startswith("Three collections")
    domains = described["domains"]
    assert domains[0]["name"] == "Graph"
    fields = {f["label"]: f["type"] for f in domains[0]["inputFields"]}
    assert fields["graph6"] == "string"
    assert fields["degree_sequence"] == "list int"
    links = {f["label"]: f["domain"] for f in domains[0]["domainFields"]}
    assert links == {"source": "Source", "automorphism_group": "Group"}
    assert all("output" in e["query"] for e in described["examples"])
