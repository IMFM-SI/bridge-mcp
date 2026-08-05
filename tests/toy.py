"""The toy database the type-checking, compilation, and postprocess suites share.

One domain `Graph` with a string primary key and three further fields, a second domain
linking to it, one SQL function registered under a SQL name of its own, and one
postprocess function.
"""

from collections.abc import Sequence

from bridge_mcp.mathql.database import (
    Column,
    Database,
    ForeignKey,
    PostFunction,
    Schema,
    SqlFunction,
)
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.types import BoolType, IntType, ListType, StringType

GRAPH = Schema(
    table="graph",
    columns={
        "graph6": Column("graph6", StringType(), True, ""),
        "n": Column("n", IntType(), False, ""),
        "planar": Column("planar", BoolType(), False, ""),
        "ds": Column("ds", ListType(IntType()), False, ""),
    },
    foreign_keys={},
    doc="",
)

MANIPLEX = Schema(
    table="maniplex",
    columns={
        "mid": Column("mid", IntType(), True, ""),
        "size": Column("size", IntType(), False, ""),
    },
    foreign_keys={"skeleton": ForeignKey("Graph", (("skeleton_graph6", "graph6"),), "")},
    doc="",
)


def plus(args: Sequence[object]) -> object:
    """`plus : (int, int) -> int`."""
    match args:
        case [a, b] if type(a) is int and type(b) is int:
            return a + b
        case _:
            raise MathQLError("plus expects two integers")


DATABASE = Database(
    overview="toy",
    constants=(),
    domains={"Graph": GRAPH, "Maniplex": MANIPLEX},
    examples=(),
    sql_functions=(SqlFunction("size", (StringType(),), IntType(), "length"),),
    post_functions=(PostFunction("plus", (IntType(), IntType()), IntType(), plus),),
)
