"""Checks for the query-language types and operator typing."""

from bridge_mcp.mathql.operators import BinaryOp, UnaryOp
from bridge_mcp.mathql.types import (
    BoolType,
    IntType,
    ListType,
    ProductType,
    StringType,
    binary_type,
    product_of,
    render,
    unary_type,
)


def test_render() -> None:
    assert render(IntType()) == "int"
    assert render(BoolType()) == "bool"
    assert render(StringType()) == "string"
    assert render(ListType(IntType())) == "list int"
    assert render(ProductType((IntType(), BoolType()))) == "prod [int, bool]"


def test_product_of() -> None:
    assert product_of((IntType(),)) == IntType()
    assert product_of((IntType(), BoolType())) == ProductType((IntType(), BoolType()))
    assert product_of(()) == ProductType(())


def test_equality() -> None:
    assert IntType() == IntType()
    assert ListType(IntType()) == ListType(IntType())
    assert ListType(IntType()) != ListType(BoolType())
    assert IntType() != BoolType()


def test_operator_typing() -> None:
    assert unary_type(UnaryOp.NOT) == (BoolType(), BoolType())
    assert unary_type(UnaryOp.NEG) == (IntType(), IntType())
    assert binary_type(BinaryOp.ADD) == (IntType(), IntType(), IntType())
    assert binary_type(BinaryOp.AND) == (BoolType(), BoolType(), BoolType())
