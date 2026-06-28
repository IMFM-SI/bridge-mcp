"""Checks for the graph component's tools."""

import sqlite3

import pytest

from bridge_mcp.graph.tools import (
    articulation_points,
    bridges,
    centrality,
    center,
    connected_components,
    coloring,
    draw,
    edge_list,
    graph6_from_adjacency,
    graph6_from_edges,
    invariants,
    is_induced_subgraph,
    is_isomorphic,
    is_subgraph,
    max_clique,
    max_independent_set,
    maximum_matching,
    minimum_vertex_cover,
    optimal_coloring,
    periphery,
    spanning_tree,
)
from bridge_mcp.mathql.databases.math_data import database
from bridge_mcp.mathql.execute import database_path, run_query

TRIANGLE = "Bw"  # C3
C7 = "FCp`_"  # the 7-cycle
K4 = "C~"  # the complete graph on 4 vertices
PATH4 = graph6_from_edges(4, [[0, 1], [1, 2], [2, 3]])  # P4


# --- construction ---


def test_graph6_from_edges() -> None:
    assert graph6_from_edges(3, [[0, 1], [0, 2], [1, 2]]) == TRIANGLE
    assert edge_list(PATH4) == {"num_vertices": 4, "edges": [[0, 1], [1, 2], [2, 3]]}


def test_graph6_from_adjacency() -> None:
    assert graph6_from_adjacency([[0, 1, 1], [1, 0, 1], [1, 1, 0]]) == TRIANGLE


# --- decoding ---


def test_edge_list_and_components() -> None:
    assert edge_list(TRIANGLE) == {"num_vertices": 3, "edges": [[0, 1], [0, 2], [1, 2]]}
    assert connected_components(K4) == [[0, 1, 2, 3]]


# --- invariants ---


def test_invariants_c7() -> None:
    inv = invariants(C7)
    assert inv["num_vertices"] == 7
    assert inv["num_edges"] == 7
    assert inv["girth"] == 7
    assert inv["is_connected"] is True
    assert inv["is_regular"] is True
    assert inv["chromatic_number"] == 3
    assert inv["clique_number"] == 2
    assert inv["independence_number"] == 3
    assert inv["diameter"] == 3


def test_invariants_match_database() -> None:
    db = database_path()
    if not db.exists():
        pytest.skip(f"{db} not present")
    connection = sqlite3.connect(db)
    rows = run_query(
        connection,
        database,
        {
            "domains": [["g", "Graph8"]],
            "output": ["g"],
            "condition": "g.num_vertices == 3 && g.num_edges == 3",
        },
    )
    connection.close()
    whole = rows[0]["g"]
    expected = {label: value for label, value in whole.items() if label != "graph6"}
    assert invariants(TRIANGLE) == expected


# --- witnesses ---


def test_clique_independence_cover() -> None:
    assert max_clique(K4) == [0, 1, 2, 3]
    assert len(max_independent_set(K4)) == 1
    assert minimum_vertex_cover(TRIANGLE) == [] or len(minimum_vertex_cover(TRIANGLE)) == 2
    assert len(minimum_vertex_cover(C7)) == 4


def test_colorings() -> None:
    assert coloring(K4)["num_colors"] == 4
    assert optimal_coloring(C7)["num_colors"] == 3
    assert optimal_coloring(K4)["num_colors"] == 4


def test_matching_and_spanning_tree() -> None:
    assert len(maximum_matching(C7)) == 3
    assert len(spanning_tree(C7)) == 6  # n - 1 for a connected graph
    assert len(spanning_tree(TRIANGLE)) == 2


def test_center_periphery() -> None:
    assert center(C7) == list(range(7))  # vertex-transitive: every vertex is central
    assert center(PATH4) == [1, 2]
    assert periphery(PATH4) == [0, 3]


def test_articulation_and_bridges() -> None:
    assert articulation_points(PATH4) == [1, 2]
    assert bridges(PATH4) == [[0, 1], [1, 2], [2, 3]]
    assert articulation_points(TRIANGLE) == []
    assert bridges(TRIANGLE) == []


# --- relations ---


def test_isomorphism() -> None:
    relabelled = graph6_from_edges(3, [[0, 1], [1, 2], [0, 2]])
    assert is_isomorphic(TRIANGLE, relabelled)
    assert not is_isomorphic(TRIANGLE, PATH4)


def test_subgraph_vs_induced() -> None:
    edge = graph6_from_edges(2, [[0, 1]])
    two_isolated = graph6_from_edges(2, [])
    assert is_subgraph(edge, TRIANGLE)
    assert is_induced_subgraph(edge, TRIANGLE)
    assert is_subgraph(two_isolated, TRIANGLE)  # ignores edges
    assert not is_induced_subgraph(
        two_isolated, TRIANGLE
    )  # K3 has no two non-adjacent vertices


# --- centrality ---


def test_centrality() -> None:
    scores = centrality(C7, "degree")
    assert len(scores) == 7
    assert all(score == pytest.approx(2 / 6) for _, score in scores)
    with pytest.raises(ValueError):
        centrality(C7, "bogus")


# --- drawing ---


def test_draw_returns_png() -> None:
    image = draw(TRIANGLE)
    assert image.data[:4] == b"\x89PNG"
    colored = draw(TRIANGLE, [[0, 0], [1, 1], [2, 2]])
    assert colored.data[:4] == b"\x89PNG"
