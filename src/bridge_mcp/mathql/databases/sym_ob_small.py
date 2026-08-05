"""The `sym_ob_small` database: regular rank-4 maniplexes with their flag graphs,
skeleta, and canonical labelings.

`Maniplex` links through `CanonicalLabeling` to `Graph`, so reaching a maniplex's flag
graph is a two-hop chain of domain fields.
"""

from importlib import resources
from pathlib import Path

from bridge_mcp.mathql.database import Column, Database, Example, ForeignKey, Schema
from bridge_mcp.mathql.types import (
    BoolType,
    IntType,
    ListType,
    ProductType,
    StringType,
    Ty,
)


def database_path() -> Path:
    """The database file's expected location, beside the bundled `math-data.db`."""
    return Path(
        str(resources.files("bridge_mcp.mathql.databases").joinpath("sym-ob-small.db"))
    )


def _columns(rows: tuple[tuple[str, str, Ty, str], ...]) -> dict[str, Column]:
    """The column mapping from (label, column, type, doc) rows; the `id` label is the
    primary key throughout this database."""
    return {label: Column(column, ty, label == "id", doc) for label, column, ty, doc in rows}


def _foreign_keys(rows: tuple[tuple[str, str, str, str], ...]) -> dict[str, ForeignKey]:
    """The foreign-key mapping from (label, column, domain, doc) rows; every foreign
    key in this database points at the linked table's `id`."""
    return {
        label: ForeignKey(domain, ((column, "id"),), doc)
        for label, column, domain, doc in rows
    }


_GRAPH = Schema(
    table="graph",
    columns=_columns(
        (
            ("id", "id", IntType(), "the graph's identifier"),
            ("sparse6", "graph_in_sparse6", StringType(), "the graph in sparse6 encoding"),
            ("num_vertices", "order", IntType(), "order: the number of vertices"),
            ("num_edges", "size", IntType(), "size: the number of edges"),
            ("degree_sequence", "degree_sequence", ListType(IntType()), "the vertex degrees"),
        )
    ),
    foreign_keys={},
    doc="An undirected graph: a flag graph, 1-skeleton, or 1-coskeleton of a maniplex.",
)

_CANONICAL_LABELING = Schema(
    table="canonicallabeling",
    columns=_columns(
        (
            ("id", "id", IntType(), "the labeling's identifier"),
            (
                "vertex_order",
                "vertices_in_canonical_order",
                ListType(IntType()),
                "the vertices in canonical order",
            ),
        )
    ),
    foreign_keys=_foreign_keys(
        (
            ("graph", "graph_in_sparse6_id", "Graph", "the labeled graph"),
            (
                "parameters",
                "parameters_id",
                "LabelingParameters",
                "the labeling-tool configuration that produced it",
            ),
        )
    ),
    doc="A canonical vertex ordering of a graph, produced by a labeling tool.",
)

_MANIPLEX = Schema(
    table="maniplex",
    columns=_columns(
        (
            ("id", "id", IntType(), "the maniplex's identifier"),
            ("num_flags", "size", IntType(), "the number of flags"),
            (
                "schlafli_symbol",
                "schlafli_symbol",
                ProductType((IntType(), IntType(), IntType())),
                "the Schläfli symbol (p, q, r): p-gonal 2-faces, q-gonal vertex "
                "figures, r-gonal edge figures",
            ),
            (
                "generators",
                "generators",
                ProductType(
                    (
                        ListType(IntType()),
                        ListType(IntType()),
                        ListType(IntType()),
                        ListType(IntType()),
                    )
                ),
                "the connection-group generators r0, r1, r2, r3",
            ),
            ("orientable", "orientable", BoolType(), "whether the maniplex is orientable"),
            (
                "polytopality",
                "polytopality",
                StringType(),
                "'Polytopal', 'Faithful', or 'Unfaithful'",
            ),
            (
                "edge_coloring",
                "cl_fg_edge_coloring",
                StringType(),
                "the edge coloring of the flag graph, encoded",
            ),
            (
                "one_skeleton",
                "one_skeleton",
                StringType(),
                "the 1-skeleton as an adjacency description",
            ),
            (
                "one_coskeleton",
                "one_coskeleton",
                StringType(),
                "the 1-coskeleton as an adjacency description",
            ),
            (
                "color_group",
                "color_group",
                ListType(ListType(IntType())),
                "the color-symmetry group as permutations; empty when trivial",
            ),
            (
                "symmetry_type",
                "symmetry_type",
                StringType(),
                "the symmetry type; 'regular' throughout this census",
            ),
        )
    ),
    foreign_keys=_foreign_keys(
        (
            (
                "flag_graph",
                "cl_flag_graph_id",
                "CanonicalLabeling",
                "the canonically labeled flag graph",
            ),
            (
                "skeleton",
                "cl_one_skeleton_id",
                "CanonicalLabeling",
                "the canonically labeled 1-skeleton",
            ),
            (
                "coskeleton",
                "cl_one_coskeleton_id",
                "CanonicalLabeling",
                "the canonically labeled 1-coskeleton",
            ),
        )
    ),
    doc="A regular rank-4 maniplex: a set of flags with four adjacency involutions.",
)

_LABELING_PARAMETERS = Schema(
    table="clparameters",
    columns=_columns(
        (
            ("id", "id", IntType(), "the configuration's identifier"),
            ("software", "software", StringType(), "the labeling tool"),
            ("version", "version", StringType(), "the tool's version"),
            ("prefix", "prefix", StringType(), "invocation arguments before the input"),
            ("suffix", "suffix", StringType(), "invocation arguments after the input"),
        )
    ),
    foreign_keys={},
    doc="A labeling-tool configuration used to compute canonical labelings.",
)

_GRAPH_EXTERNAL_REFERENCE = Schema(
    table="graphexternalreference",
    columns=_columns(
        (
            ("id", "id", IntType(), "the reference's identifier"),
            ("source", "source", StringType(), "the external collection, e.g. 'HoG'"),
            (
                "external_id",
                "id_source",
                StringType(),
                "the identifier within that collection",
            ),
        )
    ),
    foreign_keys=_foreign_keys((("graph", "graph_id", "Graph", "the referenced graph"),)),
    doc="A cross-reference from a graph to an external census or database.",
)

database = Database(
    overview=(
        "Regular rank-4 maniplexes (32 634 of them) with their flag graphs, 1-skeleta, "
        "1-coskeleta, and canonical labelings. A maniplex links to a CanonicalLabeling "
        "through flag_graph, skeleton, and coskeleton; a labeling links to its Graph."
    ),
    constants=(),
    domains={
        "Maniplex": _MANIPLEX,
        "CanonicalLabeling": _CANONICAL_LABELING,
        "Graph": _GRAPH,
        "LabelingParameters": _LABELING_PARAMETERS,
        "GraphExternalReference": _GRAPH_EXTERNAL_REFERENCE,
    },
    examples=(
        Example(
            "orientable polytopal maniplexes of type (4, 8, 8)",
            {
                "domains": [["m", "Maniplex"]],
                "output": [["id", "id(m)"], ["flags", "m.num_flags"]],
                "condition": (
                    "m.orientable && m.polytopality == 'Polytopal' "
                    "&& m.schlafli_symbol == (4, 8, 8)"
                ),
                "limit": 5,
            },
        ),
        Example(
            "the skeleta of the smallest polytopal maniplexes, via the two-hop chain",
            {
                "domains": [["m", "Maniplex"]],
                "output": [
                    ["id", "id(m)"],
                    ["flags", "m.num_flags"],
                    ["skeleton6", "m.skeleton.graph.sparse6"],
                ],
                "condition": "m.polytopality == 'Polytopal'",
                "order": [["flags", "asc"]],
                "limit": 5,
            },
        ),
        Example(
            "self-dual maniplexes: the skeleton and coskeleton are the same graph",
            {
                "domains": [["m", "Maniplex"]],
                "output": [["id", "id(m)"], ["graph_id", "id(m.skeleton.graph)"]],
                "condition": "id(m.skeleton.graph) == id(m.coskeleton.graph)",
                "limit": 5,
            },
        ),
        Example(
            "maniplexes with a nontrivial color group, most flags first",
            {
                "domains": [["m", "Maniplex"]],
                "output": [["id", "id(m)"], ["flags", "m.num_flags"]],
                "condition": "m.color_group != []",
                "order": [["flags", "desc"]],
                "limit": 5,
            },
        ),
        Example(
            "graphs referenced in the House of Graphs, with their vertex counts",
            {
                "domains": [["r", "GraphExternalReference"]],
                "output": [["hog", "r.external_id"], ["vertices", "r.graph.num_vertices"]],
                "condition": "r.source == 'HoG'",
                "limit": 5,
            },
        ),
    ),
)
