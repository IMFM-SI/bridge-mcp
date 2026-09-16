"""A read-only connection admits a query and nothing else."""

import sqlite3
import threading
from pathlib import Path

import pytest

from bridge_mcp.connection import open_read_only, restrict_to_queries
from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import safe_alias_predicate


@pytest.fixture
def path(tmp_path: Path) -> Path:
    """A database of one table, written before anything restricts it."""
    file = tmp_path / "probe.db"
    connection = sqlite3.connect(file)
    connection.execute("CREATE TABLE graph (graph6 TEXT PRIMARY KEY, num_vertices INTEGER)")
    connection.execute("INSERT INTO graph VALUES ('A?', 2)")
    connection.commit()
    connection.close()
    return file


REFUSED = (
    "INSERT INTO graph VALUES ('B?', 3)",
    "UPDATE graph SET num_vertices = 0",
    "DELETE FROM graph",
    "DROP TABLE graph",
    "CREATE TABLE other (x)",
    "CREATE TEMP TABLE t (x)",
    "PRAGMA table_info(graph)",
    "SELECT name FROM pragma_table_info('graph')",
)

WRITES = (
    "INSERT INTO graph VALUES ('B?', 3)",
    "UPDATE graph SET num_vertices = 0",
    "DELETE FROM graph",
    "DROP TABLE graph",
    "CREATE TABLE other (x)",
    "ALTER TABLE graph ADD COLUMN extra INTEGER",
)


def test_a_query_runs(path: Path) -> None:
    connection = open_read_only(path)
    restrict_to_queries(connection)
    assert connection.execute("SELECT num_vertices FROM graph").fetchall() == [(2,)]


def test_a_query_runs_on_another_thread(path: Path) -> None:
    connection = open_read_only(path)
    restrict_to_queries(connection)
    statement = "SELECT num_vertices FROM graph"
    rows = []
    thread = threading.Thread(target=lambda: rows.extend(connection.execute(statement)))
    thread.start()
    thread.join()
    assert rows == [(2,)]


def test_the_schema_is_readable(path: Path) -> None:
    connection = open_read_only(path)
    restrict_to_queries(connection)
    statement = "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
    name, ddl = connection.execute(statement).fetchone()
    assert name == "graph"
    assert "num_vertices INTEGER" in ddl


@pytest.mark.parametrize("statement", REFUSED)
def test_everything_but_a_query_is_refused(path: Path, statement: str) -> None:
    connection = open_read_only(path)
    restrict_to_queries(connection)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        connection.execute(statement)


@pytest.mark.parametrize(
    "statement",
    (
        "ATTACH DATABASE '{other}' AS a",
        "VACUUM INTO '{other}'",
    ),
)
def test_no_statement_reaches_another_file(path: Path, statement: str) -> None:
    other = path.parent / "other.db"
    connection = open_read_only(path)
    restrict_to_queries(connection)
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(statement.format(other=other))
    assert not other.exists()


def test_the_alias_predicate_rejects_the_real_column_names(path: Path) -> None:
    connection = open_read_only(path)
    is_safe_alias = safe_alias_predicate(connection, database)
    assert not is_safe_alias("graph6")
    assert not is_safe_alias("NUM_VERTICES")
    assert not is_safe_alias("rowid")
    assert is_safe_alias("c1")


@pytest.mark.parametrize("statement", WRITES)
def test_the_open_mode_alone_refuses_a_write(path: Path, statement: str) -> None:
    connection = open_read_only(path)
    with pytest.raises(sqlite3.DatabaseError, match="readonly"):
        connection.execute(statement)


def test_the_attached_limit_alone_refuses_attach(path: Path) -> None:
    other = path.parent / "other.db"
    connection = open_read_only(path)
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(f"ATTACH DATABASE '{other}' AS a")
    assert not other.exists()


def test_an_extension_does_not_load(path: Path) -> None:
    connection = open_read_only(path)
    restrict_to_queries(connection)
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("SELECT load_extension('nonesuch')")


def test_the_alias_predicate_runs_on_a_restricted_connection(path: Path) -> None:
    connection = open_read_only(path)
    restrict_to_queries(connection)
    is_safe_alias = safe_alias_predicate(connection, database)
    assert not is_safe_alias("num_vertices")
    assert is_safe_alias("c1")
