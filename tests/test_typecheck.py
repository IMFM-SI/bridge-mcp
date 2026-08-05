"""Type-checking guards, ported from the Lean Test.lean."""

import pytest

from bridge_mcp.mathql import input as ast
from bridge_mcp.mathql.context import Context, DomainTy, InputField, Signature
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import Direction
from bridge_mcp.mathql.parser import parse_expression
from bridge_mcp.mathql.typecheck import check_query, infer
from bridge_mcp.mathql.types import BoolType, IntType, StringType

GRAPH = DomainTy(
    input_fields={
        "graph6": InputField(StringType(), True),
        "n": InputField(IntType(), False),
        "planar": InputField(BoolType(), False),
    },
    domain_fields={},
)
MANIPLEX = DomainTy(
    input_fields={"mid": InputField(IntType(), True), "size": InputField(IntType(), False)},
    domain_fields={"skeleton": "Graph"},
)
TOY = Context(
    domains={"Graph": GRAPH, "Maniplex": MANIPLEX},
    functions={"size": Signature((StringType(),), IntType())},
)


def _query(
    output: list[tuple[str, str]],
    condition: str,
    order: list[tuple[str, Direction]] | None = None,
) -> ast.Query:
    return ast.Query(
        domains=(ast.Binding("g", "Graph"), ast.Binding("h", "Graph")),
        output=tuple((name, parse_expression(e)) for name, e in output),
        condition=parse_expression(condition),
        order=(
            tuple(ast.OrderEntry(parse_expression(e), d) for e, d in order)
            if order is not None
            else None
        ),
    )


def _elaborates(
    output: list[tuple[str, str]],
    condition: str,
    order: list[tuple[str, Direction]] | None = None,
) -> bool:
    try:
        check_query(TOY, _query(output, condition, order))
    except MathQLError:
        return False
    return True


def test_well_typed() -> None:
    assert _elaborates([("n", "g.n")], "g.planar")
    assert _elaborates([("n", "g.n")], "g.n > 3")
    assert _elaborates([("a", "g.n"), ("b", "g.n")], "true")
    assert _elaborates([("a", "g.n"), ("b", "h.n")], "g.n = h.n")
    assert _elaborates([("n", "g.n")], "defined g.n")
    assert _elaborates([("n", "g.n")], "undefined g.planar || g.n > 0")


def test_id_and_obj() -> None:
    assert _elaborates([("gid", "id(g)")], "id(g) == 'abc'")
    assert _elaborates([("m", "Graph['abc'].n")], "Graph['abc'].n > 3")
    assert not _elaborates([("n", "g.n")], "id(g) == 3")  # id is string, not int
    assert not _elaborates([("g", "g")], "true")  # a bare object is not an expression
    assert not _elaborates([("n", "g.n")], "Graph[].n > 3")  # wrong number of key parts


def test_ill_typed() -> None:
    assert not _elaborates([("n", "g.n")], "g.n")  # condition is int, not bool
    assert not _elaborates([("b", "g.bogus")], "g.planar")  # unknown field
    assert not _elaborates([("n", "g.n")], "g.planar + 1")  # bool in arithmetic


def test_outputs_are_independent() -> None:
    assert not _elaborates([("m", "g.n"), ("k", "m + 1")], "true")


def test_order_sees_output_aliases() -> None:
    assert _elaborates([("m", "g.n * g.n")], "g.planar", [("m", Direction.DESC)])
    assert _elaborates([("m", "g.n")], "true", [("m + 1", Direction.ASC)])
    assert _elaborates([("id", "g.n")], "true", [("id", Direction.DESC)])  # id is ordinary
    assert not _elaborates([("m", "g.n")], "m > 0")  # but the condition does not


def test_domain_fields() -> None:
    ctx = TOY.extend_domain_ident("m", "Maniplex")
    int_ty, _ = infer(ctx, parse_expression("m.skeleton.n"))
    assert int_ty == IntType()
    string_ty, _ = infer(ctx, parse_expression("id(m.skeleton)"))
    assert string_ty == StringType()
    with pytest.raises(MathQLError):
        infer(ctx, parse_expression("m.skeleton"))  # a bare object


def test_lists_and_tuples() -> None:
    assert _elaborates([("n", "g.n")], "[g.n, g.n] == [1, 2]")
    assert _elaborates([("n", "g.n")], "(g.n, g.planar) == (1, true)")
    assert _elaborates([("n", "g.n")], "(g.n, g.planar).0 == g.n")
    assert not _elaborates([("n", "g.n")], "(g.n, g.planar) == (g.n, g.n)")  # types differ


def test_infer_directly() -> None:
    ctx = TOY.extend_domain_ident("g", "Graph")
    int_ty, _ = infer(ctx, parse_expression("g.n + 1"))
    assert int_ty == IntType()
    bool_ty, _ = infer(ctx, parse_expression("g.planar && g.n > 0"))
    assert bool_ty == BoolType()


def test_function_calls() -> None:
    assert _elaborates([("n", "g.n")], "size(g.graph6) > 2")
    assert _elaborates([("k", "size(g.graph6)")], "size(g.graph6) > size('ab')")
    assert not _elaborates([("n", "g.n")], "size(g.n) > 2")  # the argument is an int
    assert not _elaborates([("n", "g.n")], "size() > 2")  # too few arguments
    assert not _elaborates([("n", "g.n")], "size('a', 'b') > 2")  # too many
    assert not _elaborates([("n", "foo(3)")], "true")  # foo is in no function table
    assert not _elaborates([("n", "g.n")], "size(g.graph6)")  # a condition is checked at bool


def test_a_call_denotes_no_object() -> None:
    ctx = TOY.extend_domain_ident("g", "Graph")
    with pytest.raises(MathQLError):
        infer(ctx, parse_expression("size(g.graph6).n"))
