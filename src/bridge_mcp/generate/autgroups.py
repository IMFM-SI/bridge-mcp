"""Identify the automorphism groups of the small graphs as census groups.

For every graph on up to 8 vertices whose automorphism count fits the census
(order at most 127), the automorphisms are enumerated with networkx and the
group they generate is identified by GAP's `IdGroup`; the graph row then links
to the census group. Larger automorphism groups stay unidentified, so the link
is undefined there.
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess

import networkx as nx

from bridge_mcp.generate.common import DB_PATH
from bridge_mcp.generate.groups import MAX_ORDER

COLUMNS = ("aut_group_order", "aut_group_index")


def automorphism_permutations(graph6: str) -> list[str]:
    """Every automorphism, as a GAP `PermList` literal over 1-based vertices."""
    graph = nx.from_graph6_bytes(graph6.encode("ascii"))
    nodes = sorted(graph)
    matcher = nx.isomorphism.GraphMatcher(graph, graph)
    return [
        "PermList([" + ",".join(str(iso[v] + 1) for v in nodes) + "])"
        for iso in matcher.isomorphisms_iter()
    ]


def identify(gap: str, jobs: list[tuple[str, list[str]]]) -> list[tuple[int, int, str]]:
    """IdGroup for each (graph6, permutations) job: (order, index, graph6) rows."""
    lines = [
        f"id := IdGroup(Group([{', '.join(perms)}]));; "
        f'Print({k}, " ", id[1], " ", id[2], "\\n");'
        for k, (_, perms) in enumerate(jobs)
    ]
    program = (
        'SetPrintFormattingStatus("*stdout*", false);;\n' + "\n".join(lines) + "\nQUIT;\n"
    )
    result = subprocess.run(
        [gap, "-q", "-b"], input=program, capture_output=True, text=True, check=True
    )
    identified = []
    for line in result.stdout.splitlines():
        if line.strip():
            k, order, index = line.split()
            identified.append((int(order), int(index), jobs[int(k)][0]))
    return identified


def ensure_columns(connection: sqlite3.Connection) -> None:
    present = {row[1] for row in connection.execute("PRAGMA table_info(graph)")}
    for column in COLUMNS:
        if column not in present:
            connection.execute(f"ALTER TABLE graph ADD COLUMN {column} INTEGER")


def main(gap: str) -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found; generate the graphs first")
    connection = sqlite3.connect(DB_PATH)
    ensure_columns(connection)
    candidates = connection.execute(
        "SELECT graph6 FROM graph WHERE num_vertices <= 8 AND automorphism_count <= ?",
        (MAX_ORDER,),
    ).fetchall()
    logging.info("identifying the automorphism groups of %d graphs", len(candidates))
    jobs = [(graph6, automorphism_permutations(graph6)) for (graph6,) in candidates]
    identified = identify(gap, jobs)
    connection.executemany(
        "UPDATE graph SET aut_group_order = ?, aut_group_index = ? WHERE graph6 = ?",
        identified,
    )
    connection.executemany(
        "INSERT OR REPLACE INTO provenance VALUES (?, ?, ?, ?)",
        [
            ("Graph", "automorphism_group", "networkx", "enumeration of the automorphisms"),
            ("Graph", "automorphism_group", "gap", "identification in the census"),
            ("Graph", "automorphism_group", "bridge-mcp", ""),
        ],
    )
    connection.commit()
    connection.close()
    logging.info("identified %d automorphism groups", len(identified))
