"""The postprocess functions the databases make callable: integer factorization with
sympy, the extremes of a list of integers, and invariants of the graph a graph6 or
sparse6 string encodes, with networkx and sympy.

A graph function takes the encoded graph as a string, so the functions compose: a
postprocess entry may pass the graph6 string another entry produced.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

import networkx
import sympy

from bridge_mcp.graph.invariants import chromatic_number, girth
from bridge_mcp.mathql.database import PostFunction
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.types import IntType, ListType, ProductType, StringType

_PAIR = ProductType((IntType(), IntType()))

_INT_LIST = ListType(IntType())

# The vertex counts above which a function refuses to run: exact linear algebra over the
# adjacency matrix, and search over vertex subsets, respectively.
_MATRIX_LIMIT = 64
_SEARCH_LIMIT = 24


def _nonempty_integers(name: str, value: object) -> list[int]:
    """`value` as a non-empty list of integers."""
    match value:
        case list() as items if all(type(item) is int for item in items):
            if items:
                return items
            else:
                raise MathQLError(f"{name} expects a non-empty list")
        case _:
            raise MathQLError(f"{name} expects a list of integers, got {value!r}")


def factorize(args: Sequence[object]) -> object:
    match args:
        case [n] if type(n) is int:
            if n < 1:
                raise MathQLError(f"factorize expects a positive integer, got {n}")
            return [
                [int(prime), int(exponent)]
                for prime, exponent in sorted(sympy.factorint(n).items())
            ]
        case _:
            raise MathQLError("factorize expects one integer")


def minimum(args: Sequence[object]) -> object:
    match args:
        case [value]:
            return min(_nonempty_integers("min", value))
        case _:
            raise MathQLError("min expects one list of integers")


def maximum(args: Sequence[object]) -> object:
    match args:
        case [value]:
            return max(_nonempty_integers("max", value))
        case _:
            raise MathQLError("max expects one list of integers")


def decode(encoded: str) -> networkx.Graph:
    """The graph `encoded` encodes: sparse6 when it starts with a colon, graph6
    otherwise."""
    data = encoded.encode()
    try:
        if encoded.startswith(":"):
            return networkx.from_sparse6_bytes(data)
        else:
            return networkx.from_graph6_bytes(data)
    except Exception as error:
        raise MathQLError(f"not a graph6 or sparse6 string: {error}") from error


def _of_graph(
    name: str, compute: Callable[[networkx.Graph], object], limit: int | None = None
) -> Callable[[Sequence[object]], object]:
    """The implementation of a function of one encoded graph, refusing a graph on more
    than `limit` vertices."""

    def implementation(args: Sequence[object]) -> object:
        match args:
            case [str() as encoded]:
                graph = decode(encoded)
                if limit is not None and graph.number_of_nodes() > limit:
                    raise MathQLError(
                        f"{name} is computed only up to {limit} vertices, and this graph "
                        f"has {graph.number_of_nodes()}"
                    )
                try:
                    return compute(graph)
                except MathQLError:
                    raise
                except Exception as error:
                    raise MathQLError(f"{name} is undefined here: {error}") from error
            case _:
                raise MathQLError(f"{name} expects one graph6 or sparse6 string")

    return implementation


def _descending(values: Iterable[int]) -> list[int]:
    return sorted(values, reverse=True)


def _encode(graph: networkx.Graph) -> str:
    """The graph6 encoding of `graph`, whose vertices are 0 to n-1."""
    data: bytes = networkx.to_graph6_bytes(graph, header=False)
    return data.decode().strip()


def _edges(graph: networkx.Graph) -> list[list[int]]:
    return sorted([min(u, v), max(u, v)] for u, v in graph.edges())


def _adjacency(graph: networkx.Graph) -> list[list[int]]:
    """The adjacency matrix, rows and columns in vertex order."""
    matrix: list[list[int]] = networkx.to_numpy_array(graph, dtype=int).tolist()
    return matrix


def _char_poly(graph: networkx.Graph) -> list[int]:
    """The coefficients of the characteristic polynomial of the adjacency matrix, from
    the leading term down."""
    coefficients = sympy.Matrix(_adjacency(graph)).charpoly().all_coeffs()
    return [int(coefficient) for coefficient in coefficients]


def _num_spanning_trees(graph: networkx.Graph) -> int:
    """The number of spanning trees, as a cofactor of the Laplacian."""
    matrix = _adjacency(graph)
    if not matrix:
        raise MathQLError("numSpanningTrees expects a graph with at least one vertex")
    laplacian = sympy.Matrix(
        [
            [sum(row) if i == j else -row[j] for j in range(len(matrix))]
            for i, row in enumerate(matrix)
        ]
    )
    return int(laplacian.minor_submatrix(0, 0).det())


def _clique_number(graph: networkx.Graph) -> int:
    return max((len(clique) for clique in networkx.find_cliques(graph)), default=0)


def _independence_number(graph: networkx.Graph) -> int:
    return _clique_number(networkx.complement(graph))


_UNDEFINED_WHEN_DISCONNECTED = "; undefined when the graph is disconnected"

FUNCTIONS: tuple[PostFunction, ...] = (
    PostFunction(
        "factorize",
        (IntType(),),
        ListType(_PAIR),
        factorize,
        "the prime factorization of a positive integer, as [prime, exponent] pairs with "
        "the primes ascending; the factorization of 1 is the empty list",
    ),
    PostFunction(
        "min",
        (_INT_LIST,),
        IntType(),
        minimum,
        "the least element of a non-empty list of integers",
    ),
    PostFunction(
        "max",
        (_INT_LIST,),
        IntType(),
        maximum,
        "the greatest element of a non-empty list of integers",
    ),
    PostFunction(
        "edgeList",
        (StringType(),),
        ListType(_PAIR),
        _of_graph("edgeList", _edges),
        "the edges of the graph, each a [smaller endpoint, larger endpoint] pair, in "
        "increasing order",
    ),
    PostFunction(
        "numVertices",
        (StringType(),),
        IntType(),
        _of_graph("numVertices", lambda graph: graph.number_of_nodes()),
        "the number of vertices of the graph",
    ),
    PostFunction(
        "numEdges",
        (StringType(),),
        IntType(),
        _of_graph("numEdges", lambda graph: graph.number_of_edges()),
        "the number of edges of the graph",
    ),
    PostFunction(
        "degreeSequence",
        (StringType(),),
        _INT_LIST,
        _of_graph(
            "degreeSequence",
            lambda graph: _descending(degree for _, degree in graph.degree()),
        ),
        "the vertex degrees of the graph, sorted descending",
    ),
    PostFunction(
        "complement",
        (StringType(),),
        StringType(),
        _of_graph("complement", lambda graph: _encode(networkx.complement(graph))),
        "the complement of the graph in graph6, which the other graph functions accept "
        "in turn; its vertices keep the numbering of the argument, so the string is one "
        "encoding of the complement among many and comparing it with == asks whether "
        "two encodings agree, not whether two graphs do",
    ),
    PostFunction(
        "componentSizes",
        (StringType(),),
        _INT_LIST,
        _of_graph(
            "componentSizes",
            lambda graph: _descending(
                len(component) for component in networkx.connected_components(graph)
            ),
        ),
        "the number of vertices of each connected component, sorted descending",
    ),
    PostFunction(
        "eccentricities",
        (StringType(),),
        _INT_LIST,
        _of_graph(
            "eccentricities",
            lambda graph: _descending(networkx.eccentricity(graph).values()),
        ),
        "the vertex eccentricities, sorted descending" + _UNDEFINED_WHEN_DISCONNECTED,
    ),
    PostFunction(
        "diameter",
        (StringType(),),
        IntType(),
        _of_graph("diameter", networkx.diameter),
        "the greatest distance between two vertices" + _UNDEFINED_WHEN_DISCONNECTED,
    ),
    PostFunction(
        "radius",
        (StringType(),),
        IntType(),
        _of_graph("radius", networkx.radius),
        "the least vertex eccentricity" + _UNDEFINED_WHEN_DISCONNECTED,
    ),
    PostFunction(
        "girth",
        (StringType(),),
        IntType(),
        _of_graph("girth", girth),
        "the length of a shortest cycle; undefined when the graph is acyclic",
    ),
    PostFunction(
        "adjacencyMatrix",
        (StringType(),),
        ListType(_INT_LIST),
        _of_graph("adjacencyMatrix", _adjacency, limit=_MATRIX_LIMIT),
        f"the adjacency matrix, rows and columns in vertex order; up to "
        f"{_MATRIX_LIMIT} vertices",
    ),
    PostFunction(
        "charPoly",
        (StringType(),),
        _INT_LIST,
        _of_graph("charPoly", _char_poly, limit=_MATRIX_LIMIT),
        f"the coefficients of the characteristic polynomial of the adjacency matrix, "
        f"from the leading term down; equal coefficients mean cospectral graphs; up to "
        f"{_MATRIX_LIMIT} vertices",
    ),
    PostFunction(
        "numSpanningTrees",
        (StringType(),),
        IntType(),
        _of_graph("numSpanningTrees", _num_spanning_trees, limit=_MATRIX_LIMIT),
        f"the number of spanning trees, zero when the graph is disconnected; up to "
        f"{_MATRIX_LIMIT} vertices",
    ),
    PostFunction(
        "cliqueNumber",
        (StringType(),),
        IntType(),
        _of_graph("cliqueNumber", _clique_number, limit=_SEARCH_LIMIT),
        f"the number of vertices of a largest clique; up to {_SEARCH_LIMIT} vertices",
    ),
    PostFunction(
        "independenceNumber",
        (StringType(),),
        IntType(),
        _of_graph("independenceNumber", _independence_number, limit=_SEARCH_LIMIT),
        f"the number of vertices of a largest independent set; up to {_SEARCH_LIMIT} vertices",
    ),
    PostFunction(
        "chromaticNumber",
        (StringType(),),
        IntType(),
        _of_graph("chromaticNumber", chromatic_number, limit=_SEARCH_LIMIT),
        f"the least number of colors in a proper vertex coloring; up to "
        f"{_SEARCH_LIMIT} vertices",
    ),
)
