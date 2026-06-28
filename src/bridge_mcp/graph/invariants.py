"""Graph invariants computed with networkx, shared by the `invariants` tool and the
database generator.

`girth`, `minimal_coloring`/`chromatic_number`, and `automorphism_count` are the exact
computations networkx does not provide directly; `all_invariants` bundles the full set the
`Graph8` schema records, as JSON-serializable values.
"""

from __future__ import annotations

import itertools
import math
from collections import deque

import networkx


def degrees(graph: networkx.Graph) -> list[int]:
    return [degree for _, degree in graph.degree()]


def girth(graph: networkx.Graph) -> int | None:
    """The length of a shortest cycle, or None if the graph is acyclic."""
    best = math.inf
    for source in graph:
        distance = {source: 0}
        parent: dict[object, object] = {source: None}
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for v in graph[u]:
                if v not in distance:
                    distance[v] = distance[u] + 1
                    parent[v] = u
                    queue.append(v)
                elif v != parent[u]:
                    best = min(best, distance[u] + distance[v] + 1)
    return None if best == math.inf else int(best)


def minimal_coloring(graph: networkx.Graph) -> dict[int, int]:
    """A proper vertex coloring using exactly the chromatic number of colors.

    Backtracking, seeded at the clique number.
    """
    nodes = list(graph)

    def color_with(k: int) -> dict[int, int] | None:
        def extend(i: int, coloring: dict[int, int]) -> dict[int, int] | None:
            if i == len(nodes):
                return coloring
            u = nodes[i]
            used = {coloring[v] for v in graph[u] if v in coloring}
            for c in range(k):
                if c not in used:
                    result = extend(i + 1, {**coloring, u: c})
                    if result is not None:
                        return result
            return None

        return extend(0, {})

    lower = max((len(clique) for clique in networkx.find_cliques(graph)), default=0)
    for k in itertools.count(max(lower, 1)):
        coloring = color_with(k)
        if coloring is not None:
            return coloring
    raise AssertionError("unreachable")


def chromatic_number(graph: networkx.Graph) -> int:
    return len(set(minimal_coloring(graph).values()))


def automorphism_count(graph: networkx.Graph) -> int:
    """The order of the automorphism group, by enumeration (small graphs only)."""
    matcher = networkx.isomorphism.GraphMatcher(graph, graph)
    return sum(1 for _ in matcher.isomorphisms_iter())


def all_invariants(graph: networkx.Graph) -> dict[str, object]:
    """The full `Graph8` invariant set as JSON-serializable values."""
    degree_list = degrees(graph)
    connected = networkx.is_connected(graph)
    return {
        "num_vertices": graph.number_of_nodes(),
        "num_edges": graph.number_of_edges(),
        "degree_sequence": sorted(degree_list, reverse=True),
        "min_degree": min(degree_list, default=0),
        "max_degree": max(degree_list, default=0),
        "is_regular": networkx.is_regular(graph),
        "num_components": networkx.number_connected_components(graph),
        "is_connected": connected,
        "diameter": networkx.diameter(graph) if connected else None,
        "radius": networkx.radius(graph) if connected else None,
        "girth": girth(graph),
        "is_tree": networkx.is_tree(graph),
        "is_forest": networkx.is_forest(graph),
        "is_bipartite": networkx.is_bipartite(graph),
        "is_planar": networkx.check_planarity(graph)[0],
        "is_eulerian": networkx.is_eulerian(graph),
        "num_triangles": sum(networkx.triangles(graph).values()) // 3,
        "clique_number": max((len(c) for c in networkx.find_cliques(graph)), default=0),
        "independence_number": max(
            (len(c) for c in networkx.find_cliques(networkx.complement(graph))), default=0
        ),
        "chromatic_number": chromatic_number(graph),
        "automorphism_count": automorphism_count(graph),
    }
