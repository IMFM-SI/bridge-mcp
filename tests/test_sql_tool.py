"""Checks for the `sql` tool: the rows it returns, and the errors it raises."""

import asyncio
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

from bridge_mcp import databases
from bridge_mcp.connection import open_read_only, restrict_to_queries
from bridge_mcp.databases import Open
from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.sql import tools


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FastMCP]:
    """A server serving the `sql` tool over one temporary database."""
    file = tmp_path / "probe.db"
    writer = sqlite3.connect(file)
    writer.execute("CREATE TABLE graph (graph6 TEXT PRIMARY KEY, num_vertices INTEGER)")
    writer.execute("CREATE TABLE blobs (payload BLOB)")
    writer.execute("INSERT INTO graph VALUES ('A?', 2), ('B?', 3)")
    writer.execute("INSERT INTO blobs VALUES (x'0f10')")
    writer.commit()
    writer.close()
    connection = open_read_only(file)
    restrict_to_queries(connection)
    opened = Open(database, connection, lambda name: True)
    monkeypatch.setattr(databases, "DATABASES", {"probe": opened})
    mcp = FastMCP("test")
    tools.register(mcp)
    yield mcp
    connection.close()


def call(app: FastMCP, **arguments: Any) -> Any:
    """The structured result of one `sql` call."""
    result = asyncio.run(app.call_tool("sql", arguments))
    return result[1] if isinstance(result, tuple) else None


def test_rows_carry_their_column_names(app: FastMCP) -> None:
    statement = "SELECT graph6, num_vertices FROM graph ORDER BY graph6"
    assert call(app, statement=statement) == {
        "result": [
            [["graph6", "A?"], ["num_vertices", 2]],
            [["graph6", "B?"], ["num_vertices", 3]],
        ]
    }


def test_a_computed_column_takes_the_name_the_statement_gives_it(app: FastMCP) -> None:
    statement = "SELECT count(*) AS total FROM graph"
    assert call(app, statement=statement) == {"result": [[["total", 2]]]}


def test_the_schema_comes_from_sqlite_master(app: FastMCP) -> None:
    statement = "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    assert call(app, statement=statement) == {
        "result": [[["name", "blobs"]], [["name", "graph"]]]
    }


def test_a_blob_arrives_as_hexadecimal_text(app: FastMCP) -> None:
    assert call(app, statement="SELECT payload FROM blobs") == {
        "result": [[["payload", "0f10"]]]
    }


def test_a_statement_selecting_nothing_returns_no_rows(app: FastMCP) -> None:
    statement = "SELECT graph6 FROM graph WHERE num_vertices = 99"
    assert call(app, statement=statement) == {"result": []}


def test_the_tool_runs_where_the_connection_was_opened(app: FastMCP) -> None:
    opened = databases.DATABASES["probe"]
    statement = "SELECT num_vertices FROM graph LIMIT 1"
    asyncio.run(app.call_tool("sql", {"statement": statement}))
    assert threading.current_thread() is threading.main_thread()
    assert opened.connection.execute(statement).fetchone() is not None


@pytest.mark.parametrize(
    "statement",
    (
        "INSERT INTO graph VALUES ('C?', 4)",
        "DROP TABLE graph",
        "PRAGMA table_info(graph)",
        "SELECT load_extension('nonesuch')",
    ),
)
def test_a_statement_beyond_a_query_is_reported(app: FastMCP, statement: str) -> None:
    with pytest.raises(Exception):  # noqa: B017
        call(app, statement=statement)


def test_a_malformed_statement_is_reported(app: FastMCP) -> None:
    with pytest.raises(Exception):  # noqa: B017
        call(app, statement="SELECT FROM")


def test_an_unknown_database_is_reported(app: FastMCP) -> None:
    with pytest.raises(Exception):  # noqa: B017
        call(app, statement="SELECT 1", database="nosuch")
