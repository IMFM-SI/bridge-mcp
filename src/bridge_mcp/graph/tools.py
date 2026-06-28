"""The graph component's tools, networkx-backed.

A `graph6` string encodes a graph; these tools build one from an edge list or adjacency
matrix, decode and analyze any graph6, compare graphs, and draw one. Vertices are numbered
0..n-1.
"""

import math
from collections.abc import Callable
from typing import Any

import networkx

from mcp.server.fastmcp import FastMCP

from bridge_mcp.graph.invariants import all_invariants, minimal_coloring

INSTRUCTIONS = """## Graph tools
A `graph6` string encodes a graph (vertices 0..n-1). Build one from a graph you have, or
analyze and compare any graph6, or draw a graph for quick visual inspection:
- construct: `graph6_from_edges`, `graph6_from_adjacency` → a graph6 string;
- decode: `edge_list`, `neighbors`, `shortest_path`, `connected_components`;
- invariants: `invariants` (the full set for any graph);
- witnesses: `max_clique`, `max_independent_set`, `minimum_vertex_cover`, `coloring`
  (greedy), `optimal_coloring` (exact), `maximum_matching`, `center`, `periphery`,
  `articulation_points`, `bridges`, `spanning_tree`;
- compare: `is_isomorphic`, `is_subgraph`, `is_induced_subgraph`;
- centrality: `centrality` (degree / betweenness / closeness / pagerank);
- visualize (unlabeled circles, for quick inspection, shown inline): `draw_graph6` (from a
  graph6) or `draw_graph` (from num_vertices and edges) → a compact SVG, optionally shaded
  by a vertex coloring; `layout` (num_vertices and edges) → vertex coordinates for drawing
  it yourself."""


def _decode(graph6: str) -> networkx.Graph:
    return networkx.from_graph6_bytes(graph6.encode())


def _build(num_vertices: int, edges: list[list[int]]) -> networkx.Graph:
    graph = networkx.Graph()
    graph.add_nodes_from(range(num_vertices))
    graph.add_edges_from(edges)
    return graph


# --- construction ---


def graph6_from_edges(num_vertices: int, edges: list[list[int]]) -> str:
    """Build a graph on vertices 0..num_vertices-1 with the given edges; return its graph6.

    The result encodes this labeling and is not necessarily nauty's canonical form, so it
    need not equal the graph6 stored in the Graph8 database; to find a graph there, query by
    invariants or use `is_isomorphic`.
    """
    graph = networkx.Graph()
    graph.add_nodes_from(range(num_vertices))
    graph.add_edges_from((u, v) for u, v in edges)
    data: bytes = networkx.to_graph6_bytes(graph, header=False)
    return data.decode().strip()


def graph6_from_adjacency(matrix: list[list[int]]) -> str:
    """Build a graph from a 0/1 adjacency matrix; return its graph6.

    The result is not necessarily nauty's canonical form, so it need not equal the graph6
    stored in the Graph8 database (see `graph6_from_edges`).
    """
    n = len(matrix)
    graph = networkx.Graph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from((i, j) for i in range(n) for j in range(i + 1, n) if matrix[i][j])
    data: bytes = networkx.to_graph6_bytes(graph, header=False)
    return data.decode().strip()


# --- decoding ---


def edge_list(graph6: str) -> dict[str, object]:
    """Decode a graph6 string to its edge list.

    Returns {"num_vertices": n, "edges": [[u, v], ...]}; the vertex count is included so
    isolated vertices are not lost.
    """
    graph = _decode(graph6)
    return {
        "num_vertices": graph.number_of_nodes(),
        "edges": sorted([min(u, v), max(u, v)] for u, v in graph.edges()),
    }


def neighbors(graph6: str, vertex: int) -> list[int]:
    """The neighbors of `vertex` (0-indexed)."""
    return sorted(_decode(graph6).neighbors(vertex))


def shortest_path(graph6: str, source: int, target: int) -> dict[str, object]:
    """A shortest path between `source` and `target` (0-indexed).

    Returns {"length": k, "path": [...]}; "path" is absent and "length" is null when the
    two vertices lie in different components.
    """
    graph = _decode(graph6)
    if networkx.has_path(graph, source, target):
        path = networkx.shortest_path(graph, source, target)
        return {"length": len(path) - 1, "path": path}
    else:
        return {"length": None}


def connected_components(graph6: str) -> list[list[int]]:
    """The connected components, each as a sorted vertex list."""
    return [sorted(component) for component in networkx.connected_components(_decode(graph6))]


# --- invariants ---


def invariants(graph6: str) -> dict[str, object]:
    """All `Graph8` invariants computed for the given graph: order, size, degree sequence,
    regularity, components, connectivity, diameter, radius, girth, the tree/forest/
    bipartite/planar/eulerian flags, triangle count, clique number, independence number,
    chromatic number, and automorphism count."""
    return all_invariants(_decode(graph6))


# --- witnesses ---


def max_clique(graph6: str) -> list[int]:
    """A maximum clique (largest set of pairwise-adjacent vertices); exact."""
    clique, _ = networkx.max_weight_clique(_decode(graph6), weight=None)
    return sorted(clique)


def max_independent_set(graph6: str) -> list[int]:
    """A maximum independent set (largest set of pairwise-nonadjacent vertices); exact."""
    clique, _ = networkx.max_weight_clique(networkx.complement(_decode(graph6)), weight=None)
    return sorted(clique)


def minimum_vertex_cover(graph6: str) -> list[int]:
    """A smallest vertex set meeting every edge (the complement of a maximum independent
    set); exact."""
    graph = _decode(graph6)
    independent, _ = networkx.max_weight_clique(networkx.complement(graph), weight=None)
    return sorted(set(graph.nodes) - set(independent))


def coloring(graph6: str) -> dict[str, object]:
    """A proper vertex coloring, computed greedily (DSATUR).

    Returns {"num_colors": k, "coloring": [[vertex, color], ...]}; proper but heuristic,
    so it may use more colors than the chromatic number (see `optimal_coloring`).
    """
    colors = networkx.greedy_color(_decode(graph6), strategy="DSATUR")
    num_colors = max(colors.values()) + 1 if colors else 0
    return {"num_colors": num_colors, "coloring": [[v, colors[v]] for v in sorted(colors)]}


def optimal_coloring(graph6: str) -> dict[str, object]:
    """An exact proper coloring using the chromatic number of colors.

    Returns {"num_colors": k, "coloring": [[vertex, color], ...]} with colors 0..k-1.
    """
    colors = minimal_coloring(_decode(graph6))
    return {
        "num_colors": len(set(colors.values())),
        "coloring": [[v, colors[v]] for v in sorted(colors)],
    }


def maximum_matching(graph6: str) -> list[list[int]]:
    """A largest set of pairwise-disjoint edges."""
    matching = networkx.max_weight_matching(_decode(graph6))
    return sorted([min(u, v), max(u, v)] for u, v in matching)


def center(graph6: str) -> list[int]:
    """The vertices of minimum eccentricity. Requires a connected graph."""
    graph = _decode(graph6)
    if not networkx.is_connected(graph):
        raise ValueError("center is undefined for a disconnected graph")
    return sorted(networkx.center(graph))


def periphery(graph6: str) -> list[int]:
    """The vertices of maximum eccentricity. Requires a connected graph."""
    graph = _decode(graph6)
    if not networkx.is_connected(graph):
        raise ValueError("periphery is undefined for a disconnected graph")
    return sorted(networkx.periphery(graph))


def articulation_points(graph6: str) -> list[int]:
    """The cut vertices: vertices whose removal increases the number of components."""
    return sorted(networkx.articulation_points(_decode(graph6)))


def bridges(graph6: str) -> list[list[int]]:
    """The cut edges: edges whose removal increases the number of components."""
    return sorted([min(u, v), max(u, v)] for u, v in networkx.bridges(_decode(graph6)))


def spanning_tree(graph6: str) -> list[list[int]]:
    """The edges of a spanning tree (a spanning forest if the graph is disconnected)."""
    tree = networkx.minimum_spanning_tree(_decode(graph6))
    return sorted([min(u, v), max(u, v)] for u, v in tree.edges())


# --- relations ---


def is_isomorphic(graph6_a: str, graph6_b: str) -> bool:
    """Whether the two graphs are isomorphic."""
    return bool(networkx.is_isomorphic(_decode(graph6_a), _decode(graph6_b)))


def is_subgraph(pattern_graph6: str, host_graph6: str) -> bool:
    """Whether `host` contains a subgraph isomorphic to `pattern` (monomorphism)."""
    matcher = networkx.isomorphism.GraphMatcher(_decode(host_graph6), _decode(pattern_graph6))
    return bool(matcher.subgraph_is_monomorphic())


def is_induced_subgraph(pattern_graph6: str, host_graph6: str) -> bool:
    """Whether `host` contains an induced subgraph isomorphic to `pattern`."""
    matcher = networkx.isomorphism.GraphMatcher(_decode(host_graph6), _decode(pattern_graph6))
    return bool(matcher.subgraph_is_isomorphic())


# --- centrality ---


def centrality(graph6: str, measure: str) -> list[list[float]]:
    """Per-vertex centrality as [[vertex, score], ...].

    `measure` is one of "degree", "betweenness", "closeness", "pagerank".
    """
    measures: dict[str, Any] = {
        "degree": networkx.degree_centrality,
        "betweenness": networkx.betweenness_centrality,
        "closeness": networkx.closeness_centrality,
        "pagerank": networkx.pagerank,
    }
    if measure not in measures:
        raise ValueError(f"unknown measure {measure!r}; expected one of {sorted(measures)}")
    scores = measures[measure](_decode(graph6))
    return [[vertex, scores[vertex]] for vertex in sorted(scores)]


# --- drawing ---


# A small categorical palette for vertex colorings, indexed by color class.
_SVG_PALETTE = [
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
]


def _svg(graph: networkx.Graph, vertex_coloring: list[list[int]] | None) -> str:
    # Hand-built rather than via matplotlib's SVG backend: that backend wraps the drawing in
    # page-sized scaffolding (a background rectangle, an axes group, clip-path definitions,
    # RDF metadata) — kilobytes of noise around a few-node graph. Emitting <line>/<circle>
    # directly keeps it minimal. Edges use `currentColor` so the drawing follows the host's
    # light/dark theme; node fills stay literal so a vertex coloring keeps its meaning.
    color_of = {vertex: color for vertex, color in (vertex_coloring or [])}
    positions = networkx.spring_layout(graph, seed=0)
    xs = [x for x, _ in positions.values()]
    ys = [y for _, y in positions.values()]
    size, radius, margin = 400.0, 12.0, 24.0

    def place(value: float, lo: float, hi: float) -> float:
        span = margin + radius
        return size / 2 if hi == lo else span + (value - lo) / (hi - lo) * (size - 2 * span)

    screen = {
        vertex: (place(x, min(xs), max(xs)), size - place(y, min(ys), max(ys)))
        for vertex, (x, y) in positions.items()
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size:g} {size:g}" '
        f'fill="none" stroke="currentColor">'
    ]
    for u, v in graph.edges():
        x1, y1 = screen[u]
        x2, y2 = screen[v]
        # trim the edge to the circle boundaries so it does not show inside the nodes
        length = math.hypot(x2 - x1, y2 - y1)
        if length > 2 * radius:
            ux, uy = (x2 - x1) / length, (y2 - y1) / length
            x1, y1 = x1 + ux * radius, y1 + uy * radius
            x2, y2 = x2 - ux * radius, y2 - uy * radius
        parts.append(f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    for vertex in graph.nodes:
        x, y = screen[vertex]
        in_coloring = vertex in color_of
        fill = _SVG_PALETTE[color_of[vertex] % len(_SVG_PALETTE)] if in_coloring else "none"
        parts.append(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:g}" fill="{fill}"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def draw_graph6(graph6: str, vertex_coloring: list[list[int]] | None = None) -> str:
    """Draw the graph6-encoded graph as a compact SVG of unlabeled circles and edges.

    For quick visual inspection, meant to be shown inline. Pass `vertex_coloring` (a list of
    [vertex, color] pairs, vertices 0..n-1) to shade vertices by color class.
    """
    return _svg(_decode(graph6), vertex_coloring)


def draw_graph(
    num_vertices: int,
    edges: list[list[int]],
    vertex_coloring: list[list[int]] | None = None,
) -> str:
    """Draw a graph on vertices 0..num_vertices-1 with the given edges as a compact SVG.

    Unlabeled circles and edges, for quick visual inspection, meant to be shown inline. Pass
    `vertex_coloring` (a list of [vertex, color] pairs) to shade vertices by color class.
    """
    return _svg(_build(num_vertices, edges), vertex_coloring)


def layout(num_vertices: int, edges: list[list[int]]) -> list[list[float]]:
    """A 2-D spring layout, as [[x, y], ...] indexed by vertex, with coordinates in [-1, 1].

    For an agent that renders the graph itself; the drawing tools use the same layout.
    """
    positions = networkx.spring_layout(_build(num_vertices, edges), seed=0)
    return [
        [round(float(positions[vertex][0]), 4), round(float(positions[vertex][1]), 4)]
        for vertex in range(num_vertices)
    ]


TOOLS: list[Callable[..., Any]] = [
    graph6_from_edges,
    graph6_from_adjacency,
    edge_list,
    neighbors,
    shortest_path,
    connected_components,
    invariants,
    max_clique,
    max_independent_set,
    minimum_vertex_cover,
    coloring,
    optimal_coloring,
    maximum_matching,
    center,
    periphery,
    articulation_points,
    bridges,
    spanning_tree,
    is_isomorphic,
    is_subgraph,
    is_induced_subgraph,
    centrality,
    draw_graph6,
    draw_graph,
    layout,
]


def register(mcp: FastMCP) -> None:
    """Register the graph tools on `mcp`."""
    for tool in TOOLS:
        mcp.add_tool(tool)
