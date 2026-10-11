"""Checks for the postprocess functions the databases declare."""

import sqlite3
from collections.abc import Iterator, Sequence

import networkx
import pytest

from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import (
    database_path,
    register_functions,
    run_query,
    safe_alias_predicate,
)
from bridge_mcp.mathql.functions import FUNCTIONS, factorize, maximum, minimum
from bridge_mcp.mathql.types import IntType, ListType, ProductType, StringType

DB = database_path()

_IMPLEMENTATIONS = {f.name: f.implementation for f in FUNCTIONS}


def call(name: str, *args: object) -> object:
    """Apply the registered implementation of `name`."""
    return _IMPLEMENTATIONS[name](args)


def graph6(graph: networkx.Graph) -> str:
    data: bytes = networkx.to_graph6_bytes(graph, header=False)
    return data.decode().strip()


TRIANGLE = "Bw"
PATH4_SPARSE6 = ":Cdv"
EDGELESS4 = "C?"


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    if not DB.exists():
        pytest.skip(f"{DB} not present; run python -m bridge_mcp.generate graphs")
    conn = sqlite3.connect(DB)
    register_functions(conn, database)
    yield conn
    conn.close()


# --- factorize, min, max ---


def test_factorize_splits_into_prime_powers() -> None:
    assert factorize([360]) == [[2, 3], [3, 2], [5, 1]]


def test_factorize_of_a_prime_is_one_power() -> None:
    assert factorize([97]) == [[97, 1]]


def test_factorize_of_one_is_the_empty_product() -> None:
    assert factorize([1]) == []


def test_factorize_rejects_a_non_positive_integer() -> None:
    with pytest.raises(MathQLError, match="positive"):
        factorize([0])


def test_factorize_rejects_a_string() -> None:
    with pytest.raises(MathQLError, match="one integer"):
        factorize(["12"])


def test_min_and_max_of_a_degree_sequence() -> None:
    assert minimum([[3, 2, 2, 1]]) == 1
    assert maximum([[3, 2, 2, 1]]) == 3


def test_min_rejects_the_empty_list() -> None:
    with pytest.raises(MathQLError, match="non-empty"):
        minimum([[]])


def test_max_rejects_a_list_of_strings() -> None:
    with pytest.raises(MathQLError, match="list of integers"):
        maximum([["a"]])


# --- decoding, shared by every graph function ---


def test_a_graph_function_reads_graph6() -> None:
    assert call("numVertices", TRIANGLE) == 3


def test_a_graph_function_reads_sparse6() -> None:
    assert call("numVertices", PATH4_SPARSE6) == 4


def test_a_graph_function_rejects_a_string_that_is_not_a_graph() -> None:
    with pytest.raises(MathQLError, match="graph6 or sparse6"):
        call("numEdges", "not a graph")


def test_a_graph_function_rejects_the_wrong_arity() -> None:
    with pytest.raises(MathQLError, match="expects one graph6 or sparse6 string"):
        call("numEdges", TRIANGLE, TRIANGLE)


# --- structure ---


def test_edge_list_of_the_triangle() -> None:
    assert call("edgeList", TRIANGLE) == [[0, 1], [0, 2], [1, 2]]


def test_edge_list_of_the_path_on_four_vertices() -> None:
    assert call("edgeList", PATH4_SPARSE6) == [[0, 1], [1, 2], [2, 3]]


def test_edge_list_of_the_edgeless_graph_is_empty() -> None:
    assert call("edgeList", EDGELESS4) == []


def test_num_edges_of_the_triangle() -> None:
    assert call("numEdges", TRIANGLE) == 3


def test_degree_sequence_is_sorted_descending() -> None:
    assert call("degreeSequence", graph6(networkx.star_graph(3))) == [3, 1, 1, 1]


def test_complement_of_the_triangle_is_edgeless() -> None:
    assert call("complement", TRIANGLE) == "B?"


def test_complement_composes_with_the_other_functions() -> None:
    complement = call("complement", graph6(networkx.path_graph(4)))
    assert isinstance(complement, str)
    assert call("numEdges", complement) == 3
    assert call("degreeSequence", complement) == [2, 2, 1, 1]


def test_adjacency_matrix_of_the_path_on_three_vertices() -> None:
    assert call("adjacencyMatrix", graph6(networkx.path_graph(3))) == [
        [0, 1, 0],
        [1, 0, 1],
        [0, 1, 0],
    ]


# --- distance and components ---


def test_component_sizes_are_sorted_descending() -> None:
    disjoint = networkx.disjoint_union(networkx.complete_graph(3), networkx.path_graph(2))
    assert call("componentSizes", graph6(disjoint)) == [3, 2]


def test_component_sizes_of_the_edgeless_graph() -> None:
    assert call("componentSizes", EDGELESS4) == [1, 1, 1, 1]


def test_diameter_and_radius_of_the_path_on_four_vertices() -> None:
    assert call("diameter", PATH4_SPARSE6) == 3
    assert call("radius", PATH4_SPARSE6) == 2


def test_eccentricities_are_sorted_descending() -> None:
    assert call("eccentricities", PATH4_SPARSE6) == [3, 3, 2, 2]


def test_diameter_of_a_disconnected_graph_is_rejected() -> None:
    with pytest.raises(MathQLError, match="diameter is undefined here"):
        call("diameter", EDGELESS4)


def test_girth_of_the_triangle() -> None:
    assert call("girth", TRIANGLE) == 3


def test_girth_of_a_tree_is_absent() -> None:
    assert call("girth", graph6(networkx.path_graph(4))) is None


# --- exact linear algebra ---


def test_char_poly_of_the_triangle() -> None:
    assert call("charPoly", TRIANGLE) == [1, 0, -3, -2]


def test_char_poly_does_not_separate_the_smallest_cospectral_pair() -> None:
    """K(1,4) and the disjoint union of a 4-cycle with a vertex have the same
    characteristic polynomial; their degree sequences differ, which is what tells them
    apart."""
    star = graph6(networkx.star_graph(4))
    cycle = graph6(networkx.disjoint_union(networkx.cycle_graph(4), networkx.empty_graph(1)))
    assert call("charPoly", star) == call("charPoly", cycle) == [1, 0, -4, 0, 0, 0]
    assert call("degreeSequence", star) == [4, 1, 1, 1, 1]
    assert call("degreeSequence", cycle) == [2, 2, 2, 2, 0]


def test_char_poly_separates_the_trees_on_four_vertices() -> None:
    assert call("charPoly", graph6(networkx.star_graph(3))) != call(
        "charPoly", graph6(networkx.path_graph(4))
    )


def test_num_spanning_trees_of_the_complete_graph_by_cayley() -> None:
    for n in range(1, 7):
        assert call("numSpanningTrees", graph6(networkx.complete_graph(n))) == n ** (n - 2)


def test_num_spanning_trees_of_a_tree_is_one() -> None:
    assert call("numSpanningTrees", graph6(networkx.path_graph(5))) == 1


def test_num_spanning_trees_of_a_disconnected_graph_is_zero() -> None:
    assert call("numSpanningTrees", EDGELESS4) == 0


# --- search, and its bound ---


def test_clique_and_independence_and_chromatic_numbers_of_the_path() -> None:
    path = graph6(networkx.path_graph(4))
    assert call("cliqueNumber", path) == 2
    assert call("independenceNumber", path) == 2
    assert call("chromaticNumber", path) == 2


def test_chromatic_number_of_the_complete_graph() -> None:
    assert call("chromaticNumber", graph6(networkx.complete_graph(5))) == 5


def test_a_search_function_refuses_a_large_graph() -> None:
    with pytest.raises(MathQLError, match="only up to 24 vertices"):
        call("chromaticNumber", graph6(networkx.empty_graph(25)))


def test_a_matrix_function_refuses_a_large_graph() -> None:
    with pytest.raises(MathQLError, match="only up to 64 vertices"):
        call("charPoly", graph6(networkx.empty_graph(65)))


# --- declaration and discovery ---


def test_the_declared_signatures() -> None:
    pair = ProductType((IntType(), IntType()))
    ints = ListType(IntType())
    declared = {f.name: (f.arg_types, f.result_ty) for f in database.post_functions}
    assert declared == {
        "factorize": ((IntType(),), ListType(pair)),
        "min": ((ints,), IntType()),
        "max": ((ints,), IntType()),
        "edgeList": ((StringType(),), ListType(pair)),
        "numVertices": ((StringType(),), IntType()),
        "numEdges": ((StringType(),), IntType()),
        "degreeSequence": ((StringType(),), ints),
        "complement": ((StringType(),), StringType()),
        "componentSizes": ((StringType(),), ints),
        "eccentricities": ((StringType(),), ints),
        "diameter": ((StringType(),), IntType()),
        "radius": ((StringType(),), IntType()),
        "girth": ((StringType(),), IntType()),
        "adjacencyMatrix": ((StringType(),), ListType(ints)),
        "charPoly": ((StringType(),), ints),
        "numSpanningTrees": ((StringType(),), IntType()),
        "cliqueNumber": ((StringType(),), IntType()),
        "independenceNumber": ((StringType(),), IntType()),
        "chromaticNumber": ((StringType(),), IntType()),
    }


def test_the_functions_are_described_with_their_signatures() -> None:
    described = database.describe()["postFunctions"]
    assert isinstance(described, list)
    signatures = {f["name"]: (f["arguments"], f["result"]) for f in described}
    assert signatures["min"] == (["list int"], "int")
    assert signatures["edgeList"] == (["string"], "list prod [int, int]")
    assert signatures["degreeSequence"] == (["string"], "list int")
    assert all(f["doc"] for f in described)


# --- over the bundled database ---


def test_graph_functions_over_the_bundled_graphs(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        safe_alias_predicate(connection, database),
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"], ["degrees", "g.degree_sequence"]],
            "condition": f"g.graph6 == '{TRIANGLE}'",
            "postprocess": [
                ["edges", "edgeList(graph6)"],
                ["spread", "max(degrees) - min(degrees)"],
                ["trees", "numSpanningTrees(graph6)"],
                ["poly", "charPoly(graph6)"],
                ["dual", "complement(graph6)"],
                ["dualEdges", "numEdges(dual)"],
            ],
        },
    )
    assert rows == [
        [
            ("graph6", "Bw"),
            ("degrees", [2, 2, 2]),
            ("edges", [[0, 1], [0, 2], [1, 2]]),
            ("spread", 0),
            ("trees", 3),
            ("poly", [1, 0, -3, -2]),
            ("dual", "B?"),
            ("dualEdges", 0),
        ]
    ]


def test_the_stored_invariants_agree_with_the_functions(
    connection: sqlite3.Connection,
) -> None:
    rows = run_query(
        connection,
        database,
        safe_alias_predicate(connection, database),
        {
            "domains": [["g", "Graph"]],
            "output": [
                ["graph6", "g.graph6"],
                ["vertices", "g.num_vertices"],
                ["edges", "g.num_edges"],
                ["degrees", "g.degree_sequence"],
                ["chromatic", "g.chromatic_number"],
            ],
            "condition": "g.num_vertices == 6 && g.is_connected",
            "postprocess": [
                ["sameVertices", "numVertices(graph6) == vertices"],
                ["sameEdges", "numEdges(graph6) == edges"],
                ["sameDegrees", "degreeSequence(graph6) == degrees"],
                ["sameChromatic", "chromaticNumber(graph6) == chromatic"],
            ],
        },
    )
    assert rows, "expected connected graphs on six vertices"
    for row in rows:
        entries = dict(row)
        assert entries["sameVertices"] is True
        assert entries["sameEdges"] is True
        assert entries["sameDegrees"] is True
        assert entries["sameChromatic"] is True


def test_factorize_over_the_group_orders(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        safe_alias_predicate(connection, database),
        {
            "domains": [["g", "Group"]],
            "output": [["order", "g.order"]],
            "condition": "g.order == 12",
            "limit": 1,
            "postprocess": [["factorization", "factorize(order)"]],
        },
    )
    assert rows == [[("order", 12), ("factorization", [[2, 2], [3, 1]])]]


def test_a_failing_call_yields_null(connection: sqlite3.Connection) -> None:
    rows = run_query(
        connection,
        database,
        safe_alias_predicate(connection, database),
        {
            "domains": [["g", "Graph"]],
            "output": [["graph6", "g.graph6"]],
            "condition": f"g.graph6 == '{TRIANGLE}'",
            "postprocess": [["edges", "edgeList('not a graph')"]],
        },
    )
    assert rows == [[("graph6", "Bw"), ("edges", None)]]


def test_a_call_at_the_wrong_type_is_rejected(connection: sqlite3.Connection) -> None:
    with pytest.raises(MathQLError, match="int"):
        run_query(
            connection,
            database,
            safe_alias_predicate(connection, database),
            {
                "domains": [["g", "Graph"]],
                "output": [["graph6", "g.graph6"]],
                "postprocess": [["bad", "factorize(graph6)"]],
            },
        )


def test_a_postprocess_function_is_not_callable_in_the_condition(
    connection: sqlite3.Connection,
) -> None:
    with pytest.raises(MathQLError, match="unknown function"):
        run_query(
            connection,
            database,
            safe_alias_predicate(connection, database),
            {
                "domains": [["g", "Graph"]],
                "output": [["graph6", "g.graph6"]],
                "condition": "numEdges(g.graph6) == 3",
            },
        )


def test_every_declared_function_rejects_arguments_of_the_wrong_kind() -> None:
    for function in FUNCTIONS:
        arguments: Sequence[object] = tuple(object() for _ in function.arg_types)
        with pytest.raises(MathQLError):
            function.implementation(arguments)
