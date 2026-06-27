"""Type-checking guards, ported from the Lean Test.lean."""

from bridge_mcp.mathql import input as ast
from bridge_mcp.mathql.context import Context, DomainSignature
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.parser import parse_expression
from bridge_mcp.mathql.typecheck import check_query, infer
from bridge_mcp.mathql.types import BoolType, IntType

GRAPH = DomainSignature(
    input_fields={"n": IntType(), "planar": BoolType()},
    output_fields=frozenset({"n"}),
)
TOY = Context(domains={"Graph": GRAPH})


def _item(text: str) -> ast.OutputItem:
    var, _, label = text.partition(".")
    return ast.OutputItem(var, label or None)


def _query(output: list[str], condition: str) -> ast.Query:
    return ast.Query(
        domains=(ast.Binding("g", "Graph"), ast.Binding("h", "Graph")),
        output=tuple(_item(o) for o in output),
        condition=parse_expression(condition),
    )


def _elaborates(output: list[str], condition: str) -> bool:
    try:
        check_query(TOY, _query(output, condition))
    except MathQLError:
        return False
    return True


def test_well_typed() -> None:
    assert _elaborates(["g.n"], "g.planar")
    assert _elaborates(["g.n"], "g.n > 3")
    assert _elaborates(["g.n", "g.n"], "true")
    assert _elaborates(["g.n", "h.n"], "g.n = h.n")
    assert _elaborates(["g.n"], "defined g.n")
    assert _elaborates(["g.n"], "undefined g.planar || g.n > 0")


def test_ill_typed() -> None:
    assert not _elaborates(["g.n"], "g.n")  # condition is int, not bool
    assert not _elaborates(["g.bogus"], "g.planar")  # unknown output field
    assert not _elaborates(["g.n"], "g.planar + 1")  # bool in arithmetic


def test_lists_and_tuples() -> None:
    assert _elaborates(["g.n"], "[g.n, g.n] == [1, 2]")
    assert _elaborates(["g.n"], "(g.n, g.planar) == (1, true)")
    assert _elaborates(["g.n"], "(g.n, g.planar).0 == g.n")
    assert not _elaborates(["g.n"], "(g.n, g.planar) == (g.n, g.n)")  # product types differ


def test_infer_directly() -> None:
    ctx = TOY.with_variables({"g": GRAPH})
    int_ty, _ = infer(ctx, parse_expression("g.n + 1"))
    assert int_ty == IntType()
    bool_ty, _ = infer(ctx, parse_expression("g.planar && g.n > 0"))
    assert bool_ty == BoolType()
