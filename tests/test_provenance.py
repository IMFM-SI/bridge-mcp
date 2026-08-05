"""Checks for the Source and Provenance domains: SQL rendering, and execution
against the bundled database."""

import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import database_path
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query
from tests.rows import rows_by_name


def _rendered(request: dict[str, Any]) -> str:
    return sql.render_query(compile_query(database, check_query(database, from_json(request))))


def test_provenance_composite_key() -> None:
    rendered = _rendered({"domains": [["p", "Provenance"]], "output": [["key", "id(p)"]]})
    assert ('json_array("p"."domain", "p"."field", "p"."source") AS "key"') in rendered


def test_provenance_source_join() -> None:
    rendered = _rendered(
        {
            "domains": [["p", "Provenance"]],
            "output": [["tool", "p.source.tool"]],
            "condition": "p.domain == 'Trait'",
        }
    )
    assert 'LEFT JOIN "source" AS "p_source" ON "p_source"."id" = "p"."source"' in rendered


def test_graph_source_join() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["src", "id(g.source)"]],
            "condition": "g.graph6 == 'Bw'",
        }
    )
    assert 'LEFT JOIN "source" AS "g_source" ON "g_source"."id" = "g"."source"' in rendered


def test_describe_includes_provenance_domains() -> None:
    described: Any = database.describe()
    domains = {d["name"]: d for d in described["domains"]}
    assert {"Source", "Provenance"} <= set(domains)
    links = {f["label"]: f["domain"] for f in domains["Provenance"]["domainFields"]}
    assert links == {"source": "Source"}


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    generated = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'provenance'"
    ).fetchone()
    if generated is None:
        conn.close()
        pytest.skip("provenance tables not present; run python -m bridge_mcp.generate")
    yield conn
    conn.close()


def test_sources_present(connection: sqlite3.Connection) -> None:
    sources = {row[0] for row in connection.execute("SELECT id FROM source")}
    assert {"geng", "networkx", "pibase", "bridge-mcp"} <= sources


def test_trait_values_have_two_sources(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["p", "Provenance"]],
            "output": [["source", "p.source.tool"], ["note", "p.note"]],
            "condition": "p.domain == 'Trait' && p.field == 'value'",
            "order": [["source", "asc"]],
        },
    )
    assert [row["source"] for row in rows] == ["bridge-mcp", "π-Base"]
    assert all(row["note"] for row in rows)


def test_graph_rows_link_their_source(connection: sqlite3.Connection) -> None:
    rows = rows_by_name(
        connection,
        database,
        {
            "domains": [["g", "Graph"]],
            "output": [["src", "id(g.source)"], ["tool", "g.source.tool"]],
            "condition": "g.graph6 == 'Bw'",
        },
    )
    assert rows == [{"src": "geng", "tool": "nauty geng"}]
