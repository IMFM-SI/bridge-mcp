#!/usr/bin/env python3
"""Generate a SQLite database of all graphs on up to N vertices (default 8),
each with a selection of invariants, using nauty's `geng` and networkx."""

from __future__ import annotations

import itertools
import json
import logging
import math
import sqlite3
import subprocess
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

import networkx as nx

DEFAULT_MAX_VERTICES = 8
GENG = "geng"
DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "bridge_mcp"
    / "mathql"
    / "databases"
    / "small-graphs.db"
)


# --- invariants not provided directly by networkx ---


def girth(graph: nx.Graph) -> int | None:
    """Length of a shortest cycle, or None if the graph is acyclic."""
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


def chromatic_number(graph: nx.Graph) -> int:
    """Exact chromatic number by backtracking, seeded at the clique number."""
    nodes = list(graph)

    def colorable(k: int) -> bool:
        def extend(i: int, coloring: dict[object, int]) -> bool:
            if i == len(nodes):
                return True
            u = nodes[i]
            used = {coloring[v] for v in graph[u] if v in coloring}
            return any(extend(i + 1, {**coloring, u: c}) for c in range(k) if c not in used)

        return extend(0, {})

    lower = max((len(c) for c in nx.find_cliques(graph)), default=0)
    return next(k for k in itertools.count(max(lower, 1)) if colorable(k))


def automorphism_count(graph: nx.Graph) -> int:
    """Order of the automorphism group, by enumeration (small graphs only)."""
    matcher = nx.isomorphism.GraphMatcher(graph, graph)
    return sum(1 for _ in matcher.isomorphisms_iter())


def degrees(graph: nx.Graph) -> list[int]:
    return [d for _, d in graph.degree()]


# --- the invariant schema: (column, sql_type, extractor) ---

Invariant = tuple[str, str, Callable[[nx.Graph], object]]

INVARIANTS: list[Invariant] = [
    ("num_vertices", "INTEGER", lambda g: g.number_of_nodes()),
    ("num_edges", "INTEGER", lambda g: g.number_of_edges()),
    # Stored minified so it compares equal to SQLite's json_array(...) output.
    (
        "degree_sequence",
        "TEXT",
        lambda g: json.dumps(sorted(degrees(g), reverse=True), separators=(",", ":")),
    ),
    ("min_degree", "INTEGER", lambda g: min(degrees(g), default=0)),
    ("max_degree", "INTEGER", lambda g: max(degrees(g), default=0)),
    ("is_regular", "INTEGER", lambda g: int(nx.is_regular(g))),
    ("num_components", "INTEGER", lambda g: nx.number_connected_components(g)),
    ("is_connected", "INTEGER", lambda g: int(nx.is_connected(g))),
    ("diameter", "INTEGER", lambda g: nx.diameter(g) if nx.is_connected(g) else None),
    ("radius", "INTEGER", lambda g: nx.radius(g) if nx.is_connected(g) else None),
    ("girth", "INTEGER", girth),
    ("is_tree", "INTEGER", lambda g: int(nx.is_tree(g))),
    ("is_forest", "INTEGER", lambda g: int(nx.is_forest(g))),
    ("is_bipartite", "INTEGER", lambda g: int(nx.is_bipartite(g))),
    ("is_planar", "INTEGER", lambda g: int(nx.check_planarity(g)[0])),
    ("is_eulerian", "INTEGER", lambda g: int(nx.is_eulerian(g))),
    ("num_triangles", "INTEGER", lambda g: sum(nx.triangles(g).values()) // 3),
    (
        "clique_number",
        "INTEGER",
        lambda g: max((len(c) for c in nx.find_cliques(g)), default=0),
    ),
    (
        "independence_number",
        "INTEGER",
        lambda g: max((len(c) for c in nx.find_cliques(nx.complement(g))), default=0),
    ),
    ("chromatic_number", "INTEGER", chromatic_number),
    ("automorphism_count", "INTEGER", automorphism_count),
]

COLUMNS: list[tuple[str, str]] = [("graph6", "TEXT")] + [
    (name, ty) for name, ty, _ in INVARIANTS
]


def generate(n: int) -> list[str]:
    """All non-isomorphic graphs on `n` vertices, as graph6 strings."""
    result = subprocess.run([GENG, str(n)], capture_output=True, text=True, check=True)
    return result.stdout.split()


def row_for(graph6: str) -> list[object]:
    graph = nx.from_graph6_bytes(graph6.encode("ascii"))
    return [graph6] + [extract(graph) for _, _, extract in INVARIANTS]


def main(max_vertices: int) -> None:
    if DB_PATH.exists():
        raise SystemExit(f"refusing to overwrite existing database {DB_PATH}")
    logging.info("creating %s, graphs on up to %d vertices", DB_PATH, max_vertices)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute(
        "CREATE TABLE graph (id INTEGER PRIMARY KEY, "
        + ", ".join(f'"{name}" {ty}' for name, ty in COLUMNS)
        + ")"
    )
    insert = (
        f"INSERT INTO graph ({', '.join(name for name, _ in COLUMNS)}) "
        f"VALUES ({', '.join('?' for _ in COLUMNS)})"
    )
    for n in range(1, max_vertices + 1):
        graph6s = generate(n)
        logging.info("n = %d: %d graphs, computing invariants", n, len(graph6s))
        connection.executemany(insert, (row_for(g6) for g6 in graph6s))
        connection.commit()
    connection.close()
    logging.info("done, wrote %s", DB_PATH)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S"
    )
    main(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MAX_VERTICES)
