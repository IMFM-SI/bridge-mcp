"""Checks for the graph component's tools, on K4 and the 7-cycle C7."""

from bridge_mcp.graph.tools import (
    coloring,
    connected_components,
    edge_list,
    max_clique,
    max_independent_set,
)

K4 = "C~"  # the complete graph on 4 vertices
C7 = "FCp`_"  # the cycle on 7 vertices


def test_edge_list_triangle() -> None:
    assert edge_list("Bw") == {"num_vertices": 3, "edges": [[0, 1], [0, 2], [1, 2]]}


def test_k4() -> None:
    assert max_clique(K4) == [0, 1, 2, 3]
    assert len(max_independent_set(K4)) == 1
    assert connected_components(K4) == [[0, 1, 2, 3]]
    assert coloring(K4)["num_colors"] == 4


def test_c7() -> None:
    decoded = edge_list(C7)
    assert decoded["num_vertices"] == 7
    assert len(decoded["edges"]) == 7
    assert len(max_independent_set(C7)) == 3
    assert coloring(C7)["num_colors"] == 3
