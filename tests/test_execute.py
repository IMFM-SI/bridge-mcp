"""End-to-end checks against the bundled database, skipped when it is absent."""

import dataclasses
import sqlite3
from collections.abc import Callable, Iterator

import pytest

from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import database_path, run_query, safe_alias_predicate
from tests.toy import DATABASE as TOY

DB = database_path()


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    if not DB.exists():
        pytest.skip(f"{DB} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(DB)
    yield conn
    conn.close()


@pytest.fixture
def is_safe_alias(connection: sqlite3.Connection) -> Callable[[str], bool]:
    return safe_alias_predicate(connection, database)


def test_triangle(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"], ["num_edges", "g.num_edges"]],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows == [[("graph6", "Bw"), ("num_edges", 3)]]


def test_trees_on_five(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"]],
            "condition": "g.num_vertices == 5 && g.is_tree",
        },
    )
    assert len(rows) == 3


def test_degree_sequence_equality(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"], ["degrees", "g.degree_sequence"]],
            "condition": "g.degree_sequence == [2, 2, 2]",
        },
    )
    assert rows == [[("graph6", "Bw"), ("degrees", [2, 2, 2])]]


def test_id_output(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [["gid", "id(g)"]],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert rows == [[("gid", "Bw")]]


def test_null_becomes_none(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [["diameter", "g.diameter"]],
            "condition": "!g.is_connected && g.num_vertices == 2",
        },
    )
    assert rows == [[("diameter", None)]]


def test_order_by_alias(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [["g6", "id(g)"], ["spread", "g.max_degree - g.min_degree"]],
            "condition": "g.num_vertices == 5",
            "order": [["spread", "desc"]],
            "limit": 3,
        },
    )
    assert [dict(row)["spread"] for row in rows] == [3, 3, 3]


def test_a_row_is_pairs_in_output_order(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [[name, "g.num_edges"] for name in ("zeta", "alpha", "mu", "beta")],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    assert [name for name, _ in rows[0]] == ["zeta", "alpha", "mu", "beta"]


def test_a_repeated_output_name_is_rejected(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    with pytest.raises(MathQLError):
        run_query(
            connection,
            database,
            is_safe_alias,
            {
                "domains": [["g", "Graph"]],
                "output": [["n", "g.num_vertices"], ["n", "g.num_edges"]],
            },
        )


def test_postprocess_appends_its_columns(connection: sqlite3.Connection) -> None:
    with_plus = dataclasses.replace(database, post_functions=TOY.post_functions)
    rows = run_query(
        connection,
        with_plus,
        safe_alias_predicate(connection, with_plus),
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "g.num_vertices"]],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
            "postprocess": [["k", "plus(n, 1)"], ["m", "k * 2"]],
        },
    )
    assert rows == [[("n", 3), ("k", 4), ("m", 8)]]


def test_the_two_stages_agree_on_the_same_row(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    """`defined` and a list comparison answer alike in a condition and in postprocess."""
    request = {
        "domains": [["g", "Graph"]],
        "output": [
            ["d", "g.diameter"],
            ["ds", "g.degree_sequence"],
            ["in_sql_defined", "defined g.diameter"],
            ["in_sql_equal", "g.degree_sequence == [2, 2, 2]"],
        ],
        "condition": "g.num_vertices <= 3",
        "postprocess": [
            ["in_post_defined", "defined d"],
            ["in_post_equal", "ds == [2, 2, 2]"],
        ],
    }
    rows = [dict(row) for row in run_query(connection, database, is_safe_alias, request)]
    assert rows
    assert all(row["in_sql_defined"] == row["in_post_defined"] for row in rows)
    assert all(row["in_sql_equal"] == row["in_post_equal"] for row in rows)
    assert {row["in_post_defined"] for row in rows} == {True, False}  # both cases occur


def test_a_query_over_constants_touches_no_table(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {"domains": [], "output": [["x", "2 + 2"], ["y", "'hi'"]]},
    )
    assert rows == [[("x", 4), ("y", "hi")]]


def test_postprocess_alone_is_a_query(connection: sqlite3.Connection) -> None:
    with_plus = dataclasses.replace(database, post_functions=TOY.post_functions)
    rows = run_query(
        connection,
        with_plus,
        safe_alias_predicate(connection, with_plus),
        {"domains": [], "output": [], "postprocess": [["k", "plus(2, 2)"]]},
    )
    assert rows == [[("k", 4)]]


def test_a_false_condition_leaves_no_row(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    assert (
        run_query(
            connection,
            database,
            is_safe_alias,
            {"domains": [], "output": [], "condition": "false"},
        )
        == []
    )


def test_naming_no_column_keeps_one_row_per_match(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    with_plus = dataclasses.replace(database, post_functions=TOY.post_functions)
    request: dict[str, object] = {
        "domains": [["g", "Graph"]],
        "output": [],
        "condition": "g.num_vertices == 3",
        "postprocess": [["k", "plus(1, 1)"]],
    }
    rows = run_query(
        connection, with_plus, safe_alias_predicate(connection, with_plus), request
    )
    counted = run_query(
        connection,
        database,
        is_safe_alias,
        {**request, "output": [["n", "g.num_vertices"]], "postprocess": []},
    )
    assert len(rows) == len(counted) == 4
    assert rows[0] == [("k", 2)]


DIVISIONS = ((7, 2, 3), (-7, 2, -3), (7, -2, -3), (-7, -2, 3), (1, 2, 0), (0, 5, 0))


@pytest.mark.parametrize(("left", "right", "quotient"), DIVISIONS)
def test_division_truncates_toward_zero_in_both_stages(
    connection: sqlite3.Connection,
    is_safe_alias: Callable[[str], bool],
    left: int,
    right: int,
    quotient: int,
) -> None:
    """The database and the postprocess evaluator compute the same quotient."""

    def literal(n: int) -> str:
        return f"({n})" if n < 0 else str(n)

    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [
                ["a", literal(left)],
                ["b", literal(right)],
                ["by_database", f"{literal(left)} / {literal(right)}"],
            ],
            "condition": "g.num_vertices == 1",
            "postprocess": [["by_evaluator", "a / b"]],
        },
    )
    assert dict(rows[0]) == {
        "a": left,
        "b": right,
        "by_database": quotient,
        "by_evaluator": quotient,
    }


def test_a_zero_divisor_has_no_value_in_either_stage(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    rows = run_query(
        connection,
        database,
        is_safe_alias,
        {
            "domains": [["g", "Graph"]],
            "output": [["a", "7"], ["b", "0"], ["by_database", "7 / 0"]],
            "condition": "g.num_vertices == 1",
            "postprocess": [["by_evaluator", "a / b"]],
        },
    )
    assert dict(rows[0]) == {"a": 7, "b": 0, "by_database": None, "by_evaluator": None}


def test_a_zero_divisor_is_undefined_in_a_condition(
    connection: sqlite3.Connection, is_safe_alias: Callable[[str], bool]
) -> None:
    request = {
        "domains": [["g", "Graph"]],
        "output": [["g6", "id(g)"]],
        "condition": "g.num_vertices == 3 && undefined (g.num_edges / (g.num_vertices - 3))",
    }
    assert len(run_query(connection, database, is_safe_alias, request)) == 4
