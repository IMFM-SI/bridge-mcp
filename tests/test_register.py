"""Checks for registering the implemented SQL functions on a connection."""

import dataclasses
import sqlite3
from collections.abc import Iterator, Sequence

import pytest

from bridge_mcp.mathql.database import SqlFunction
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import register_functions
from bridge_mcp.mathql.types import BoolType, IntType, ListType
from tests.toy import DATABASE as TOY


def contains(args: Sequence[object]) -> object:
    match args:
        case [list() as items, int() as item]:
            return item in items
        case _:
            raise MathQLError("contains expects a list and an integer")


def up_to(args: Sequence[object]) -> object:
    match args:
        case [int() as n] if n >= 0:
            return list(range(n))
        case _:
            raise MathQLError("upTo expects a non-negative integer")


DATABASE = dataclasses.replace(
    TOY,
    sql_functions=(
        *TOY.sql_functions,
        SqlFunction(
            "contains",
            (ListType(IntType()), IntType()),
            BoolType(),
            "toy_contains",
            implementation=contains,
        ),
        SqlFunction(
            "upTo", (IntType(),), ListType(IntType()), "toy_up_to", implementation=up_to
        ),
    ),
)


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    register_functions(conn, DATABASE)
    yield conn
    conn.close()


def select(connection: sqlite3.Connection, expression: str) -> object:
    return connection.execute(f"SELECT {expression}").fetchone()[0]


def test_a_list_argument_is_decoded_and_a_boolean_result_encoded(
    connection: sqlite3.Connection,
) -> None:
    assert select(connection, "toy_contains('[1,2,3]', 2)") == 1
    assert select(connection, "toy_contains('[1,2,3]', 5)") == 0


def test_a_list_result_is_encoded_as_json(connection: sqlite3.Connection) -> None:
    assert select(connection, "toy_up_to(3)") == "[0,1,2]"


def test_a_failing_call_is_null(connection: sqlite3.Connection) -> None:
    assert select(connection, "toy_up_to(-1)") is None
    assert select(connection, "toy_contains('not json', 1)") is None


def test_a_null_argument_gives_null(connection: sqlite3.Connection) -> None:
    assert select(connection, "toy_up_to(NULL)") is None


def test_a_function_without_implementation_is_left_to_sqlite(
    connection: sqlite3.Connection,
) -> None:
    assert select(connection, "length('abc')") == 3


def test_a_repeated_call_is_computed_once() -> None:
    calls: list[object] = []

    def square(args: Sequence[object]) -> object:
        calls.append(args[0])
        return args[0] * args[0] if type(args[0]) is int else None

    function = SqlFunction("sq", (IntType(),), IntType(), "toy_sq", implementation=square)
    connection = sqlite3.connect(":memory:")
    register_functions(connection, dataclasses.replace(TOY, sql_functions=(function,)))
    statement = (
        "SELECT toy_sq(n) FROM (SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3) "
        "WHERE toy_sq(n) > 1"
    )
    assert connection.execute(statement).fetchall() == [(4,), (9,)]
    assert sorted(calls) == [1, 2, 3]
    connection.close()
