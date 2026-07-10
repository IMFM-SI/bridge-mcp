"""Add the Cayley graphs of the group census to the graph table.

For every group of order up to `MAX_ORDER`, GAP emits the undirected simple
Cayley graph on a minimal generating set (edges by right multiplication,
identity excluded); nauty's `labelg` canonicalizes the graph6 form, which is
then keyed into the graph table — reusing an existing row when the graph is
already present — with the cheap invariants computed and the exponential ones
left NULL. Each group row records its generators and its graph.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
from typing import Any

import networkx as nx

from bridge_mcp.generate.common import (
    DB_PATH,
    bridge_mcp_source,
    compact,
    record_sources,
)
from bridge_mcp.generate.graphs import INVARIANTS

LABELG = "labelg"
MAX_ORDER = 100

EXPENSIVE = frozenset(
    {"chromatic_number", "clique_number", "independence_number", "automorphism_count"}
)

GAP_PROGRAM = r"""
SetPrintFormattingStatus("*stdout*", false);;
for n in [1..MAX_ORDER] do
  for i in [1..NumberSmallGroups(n)] do
    G := SmallGroup(n, i);
    if IsSolvableGroup(G) then
      generators := MinimalGeneratingSet(G);
    else
      generators := SmallGeneratingSet(G);
    fi;
    elements := Elements(G);
    edges := [];
    for v in [1..Length(elements)] do
      for s in generators do
        w := Position(elements, elements[v] * s);
        if v < w then Add(edges, [v, w]); elif w < v then Add(edges, [w, v]); fi;
      od;
    od;
    Print("{\"order\":", n,
      ",\"index\":", i,
      ",\"generators\":[",
      JoinStringsWithSeparator(
        List(generators, g -> Concatenation("\"", String(g), "\"")), ","),
      "]",
      ",\"vertices\":", Length(elements),
      ",\"edges\":", Set(edges),
      "}\n");
  od;
od;
QUIT;
"""


def cayley_records(gap: str) -> list[dict[str, Any]]:
    """One record per group of order up to `MAX_ORDER`: generators and edges."""
    program = GAP_PROGRAM.replace("MAX_ORDER", str(MAX_ORDER))
    result = subprocess.run(
        [gap, "-q", "-b"], input=program, capture_output=True, text=True, check=True
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def cayley_graph(record: dict[str, Any]) -> nx.Graph:
    """The Cayley graph of one record, on vertices 0..n-1."""
    graph = nx.Graph()
    graph.add_nodes_from(range(record["vertices"]))
    graph.add_edges_from((v - 1, w - 1) for v, w in record["edges"])
    return graph


def canonical(graph6s: list[str]) -> list[str]:
    """The canonical graph6 forms, via nauty's `labelg`, in input order."""
    result = subprocess.run(
        [LABELG],
        input="".join(line + "\n" for line in graph6s),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


def graph_row(graph6: str) -> list[object]:
    """A graph-table row for a Cayley graph: cheap invariants, expensive ones NULL."""
    graph = nx.from_graph6_bytes(graph6.encode("ascii"))
    if graph.number_of_nodes() <= 8:
        raise ValueError(f"{graph6}: small graphs must already be in the table")
    return (
        [graph6]
        + [None if name in EXPENSIVE else extract(graph) for name, _, extract in INVARIANTS]
        + ["cayley"]
    )


def main(gap: str) -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found; generate the graphs first")
    logging.info("running %s over the groups of order up to %d", gap, MAX_ORDER)
    records = cayley_records(gap)
    graphs = [cayley_graph(record) for record in records]
    for record, graph in zip(records, graphs, strict=True):
        if not nx.is_connected(graph) or not nx.is_regular(graph):
            raise SystemExit(f"Cayley graph of {record['order']},{record['index']} is wrong")
    raw = [nx.to_graph6_bytes(graph, header=False).decode("ascii").strip() for graph in graphs]
    keys = canonical(raw)
    connection = sqlite3.connect(DB_PATH)
    known = {row[0] for row in connection.execute("SELECT graph6 FROM graph")}
    fresh = sorted({key for key in keys if key not in known})
    columns = ["graph6"] + [name for name, _, _ in INVARIANTS] + ["source"]
    connection.executemany(
        f"INSERT INTO graph ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        (graph_row(graph6) for graph6 in fresh),
    )
    connection.executemany(
        "UPDATE small_group SET cayley_generators = ?, cayley_graph = ? "
        'WHERE "order" = ? AND "index" = ?',
        (
            (compact(record["generators"]), key, record["order"], record["index"])
            for record, key in zip(records, keys, strict=True)
        ),
    )
    record_sources(
        connection,
        [
            (
                "cayley",
                "GAP, bridge-mcp, and nauty labelg",
                None,
                "the Cayley graphs of the group census",
                None,
                None,
            ),
            bridge_mcp_source(),
        ],
    )
    connection.executemany(
        "INSERT OR REPLACE INTO provenance VALUES (?, ?, ?, ?)",
        [
            ("Graph", "graph6", "gap", "Cayley graphs: group elements and generators"),
            ("Graph", "graph6", "bridge-mcp", "Cayley graph construction"),
        ],
    )
    connection.commit()
    connection.close()
    logging.info(
        "Cayley graphs for %d groups: %d distinct graphs, %d new rows",
        len(records),
        len(set(keys)),
        len(fresh),
    )
