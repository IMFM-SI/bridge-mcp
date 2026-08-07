"""Checks for compiling type-checked queries to SQL, over a toy database with a
foreign key."""

from collections.abc import Callable

import pytest

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.compile import compile_query
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.query import Query
from bridge_mcp.mathql.query_json import from_json
from bridge_mcp.mathql.typecheck import check_query
from tests.aliases import safe_alias
from tests.toy import DATABASE as TOY

_safe_alias = safe_alias(TOY)


def _typed(request: dict[str, object]) -> Query:
    return check_query(TOY, from_json(request))


def _rendered_by(is_safe_alias: Callable[[str], bool], request: dict[str, object]) -> str:
    return sql.render_query(compile_query(TOY, is_safe_alias, _typed(request)))


def _rendered(request: dict[str, object]) -> str:
    return _rendered_by(_safe_alias, request)


def test_fields_and_condition() -> None:
    assert (
        _rendered(
            {"domains": [["g", "Graph"]], "output": [["n", "g.n"]], "condition": "g.n > 3"}
        )
        == 'SELECT c1."n" AS c2 FROM "graph" AS c1 WHERE (c1."n" > 3)'
    )


def test_id_of_single_column_key() -> None:
    assert _rendered({"domains": [["g", "Graph"]], "output": [["gid", "id(g)"]]}) == (
        'SELECT c1."graph6" AS c2 FROM "graph" AS c1 WHERE 1'
    )


def test_domain_field_hoists_one_join() -> None:
    rendered = _rendered(
        {
            "domains": [["m", "Maniplex"]],
            "output": [["s", "m.skeleton.graph6"]],
            "condition": "m.skeleton.n > 3",
        }
    )
    assert rendered == (
        'SELECT c3."graph6" AS c2 FROM "maniplex" AS c1'
        ' LEFT JOIN "graph" AS c3 ON c3."graph6" = c1."skeleton_graph6"'
        ' WHERE (c3."n" > 3)'
    )


def test_obj_hoists_a_join() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "Graph['abc'].n"]],
            "condition": "g.n == Graph['abc'].n",
        }
    )
    assert rendered == (
        'SELECT c3."n" AS c2 FROM "graph" AS c1'
        ' LEFT JOIN "graph" AS c3 ON c3."graph6" = \'abc\''
        ' WHERE (c1."n" = c3."n")'
    )


def test_defined_on_domain_field() -> None:
    rendered = _rendered(
        {
            "domains": [["m", "Maniplex"]],
            "output": [["mid", "m.mid"]],
            "condition": "defined id(m.skeleton)",
        }
    )
    assert 'WHERE (c3."graph6" IS NOT NULL)' in rendered


def test_order_by_alias_renders_bare() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["m", "g.n * g.n"]],
            "order": [["m", "desc"]],
            "limit": 3,
        }
    )
    assert rendered == (
        'SELECT (c1."n" * c1."n") AS c2 FROM "graph" AS c1 WHERE 1 ORDER BY c2 DESC LIMIT 3'
    )


def test_a_rejected_candidate_alias_is_skipped() -> None:
    assert (
        _rendered_by(
            lambda name: name != "c1",
            {"domains": [["g", "Graph"]], "output": [["n", "g.n"]]},
        )
        == 'SELECT c2."n" AS c3 FROM "graph" AS c2 WHERE 1'
    )


def test_an_output_column_named_after_a_table_column_is_not_captured() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.n"]],
            "order": [["graph6 * 1", "asc"]],
        }
    )
    assert rendered == 'SELECT c1."n" AS c2 FROM "graph" AS c1 WHERE 1 ORDER BY (c2 * 1) ASC'
    assert "graph6" not in rendered


def test_tuples_projections_and_conditional() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["pair", "(g.n, g.planar)"], ["first", "(g.n, g.planar).0"]],
            "condition": "if g.planar then g.n > 0 else [1, 2] == [g.n, g.n]",
        }
    )
    assert 'json_array(c1."n", c1."planar") AS c2' in rendered
    assert 'json_extract(json_array(c1."n", c1."planar"), \'$[0]\') AS c3' in rendered
    assert (
        'CASE WHEN c1."planar" THEN (c1."n" > 0)'
        ' ELSE (json(json_array(1, 2)) = json(json_array(c1."n", c1."n"))) END' in rendered
    )


def test_condition_does_not_see_aliases() -> None:
    with pytest.raises(MathQLError):
        _typed({"domains": [["g", "Graph"]], "output": [["m", "g.n"]], "condition": "m > 0"})


def test_call_compiles_to_its_sql_name() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "g.n"]],
            "condition": "size(g.graph6) > 2",
        }
    )
    assert rendered.endswith('WHERE ("length"(c1."graph6") > 2)')


def test_call_nests_and_serves_as_an_output_column() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["k", "size(g.graph6)"]],
            "condition": "size(g.graph6) > size('ab')",
        }
    )
    assert '"length"(c1."graph6") AS c2' in rendered
    assert '("length"(c1."graph6") > "length"(\'ab\'))' in rendered


def test_a_call_is_legal_in_an_order_key() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "g.n"]],
            "order": [["size(g.graph6)", "desc"]],
        }
    )
    assert rendered.endswith('ORDER BY "length"(c1."graph6") DESC')


def test_a_constant_order_key_is_dropped() -> None:
    assert (
        _rendered(
            {
                "domains": [["g", "Graph"]],
                "output": [["n", "g.n"]],
                "order": [["1", "asc"]],
            }
        )
        == 'SELECT c1."n" AS c2 FROM "graph" AS c1 WHERE 1'
    )


def test_a_constant_order_key_beside_a_varying_one_leaves_one_term() -> None:
    assert (
        _rendered(
            {
                "domains": [["g", "Graph"]],
                "output": [["n", "g.n"]],
                "order": [["1", "asc"], ["g.n", "desc"]],
            }
        )
        == 'SELECT c1."n" AS c2 FROM "graph" AS c1 WHERE 1 ORDER BY c1."n" DESC'
    )


def test_order_keys_constant_in_every_shape_are_all_dropped() -> None:
    assert (
        _rendered(
            {
                "domains": [["g", "Graph"]],
                "output": [["n", "g.n"]],
                "order": [["-1", "asc"], ["!true", "desc"], ["1 + 0", "asc"]],
            }
        )
        == 'SELECT c1."n" AS c2 FROM "graph" AS c1 WHERE 1'
    )


def test_an_order_key_calling_a_database_function_is_kept() -> None:
    assert (
        _rendered(
            {
                "domains": [["g", "Graph"]],
                "output": [["n", "g.n"]],
                "order": [["size('ab')", "asc"]],
            }
        )
        == 'SELECT c1."n" AS c2 FROM "graph" AS c1 WHERE 1 ORDER BY "length"(\'ab\') ASC'
    )


def test_postprocess_contributes_nothing_to_the_sql() -> None:
    rendered = _rendered(
        {
            "domains": [["g", "Graph"]],
            "output": [["n", "g.n"]],
            "postprocess": [["k", "plus(n, 1)"]],
        }
    )
    assert rendered == 'SELECT c1."n" AS c2 FROM "graph" AS c1 WHERE 1'
    assert "k" not in rendered
    assert "plus" not in rendered


def test_a_query_over_no_table_has_no_from_clause() -> None:
    assert _rendered({"domains": [], "output": [["x", "2 + 2"]]}) == (
        "SELECT (2 + 2) AS c1 WHERE 1"
    )


def test_a_hoisted_join_over_no_table_takes_a_one_row_left_operand() -> None:
    assert _rendered({"domains": [], "output": [["n", "Graph['abc'].n"]]}) == (
        'SELECT c2."n" AS c1 FROM (SELECT 1)'
        ' LEFT JOIN "graph" AS c2 ON c2."graph6" = \'abc\' WHERE 1'
    )


def test_a_query_naming_no_column_selects_a_placeholder() -> None:
    assert (
        _rendered({"domains": [["g", "Graph"]], "output": [], "condition": "g.n > 3"})
        == 'SELECT 1 FROM "graph" AS c1 WHERE (c1."n" > 3)'
    )
    assert _rendered({"domains": [], "output": []}) == "SELECT 1 WHERE 1"
