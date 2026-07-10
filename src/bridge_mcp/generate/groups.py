"""Fill the small_group table of math-data.db from GAP's SmallGroups library.

Runs GAP on an embedded program that emits one JSON line per group of order up
to `MAX_ORDER`, and rebuilds the small_group table inside the existing
database. The Cayley-graph columns are filled by the cayley generator.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
from typing import Any

from bridge_mcp.generate.common import (
    DB_PATH,
    bridge_mcp_source,
    compact,
    record_provenance,
    record_sources,
)

GAP = "gap"
MAX_ORDER = 127

GAP_PROGRAM = r"""
SetPrintFormattingStatus("*stdout*", false);;
bool := function(b) if b then return "true"; else return "false"; fi; end;;
opt := function(x) if x = fail then return "null"; else return String(x); fi; end;;
Print("{\"gap_version\":\"", GAPInfo.Version, "\"}\n");
for n in [1..MAX_ORDER] do
  for i in [1..NumberSmallGroups(n)] do
    G := SmallGroup(n, i);
    solvable := IsSolvableGroup(G);
    nilpotent := IsNilpotentGroup(G);
    if solvable then
      generators := MinimalGeneratingSet(G);
      derived_length := DerivedLength(G);
    else
      generators := SmallGeneratingSet(G);
      derived_length := fail;
    fi;
    if nilpotent then
      nilpotency_class := NilpotencyClassOfGroup(G);
    else
      nilpotency_class := fail;
    fi;
    Print("{\"order\":", n,
      ",\"index\":", i,
      ",\"structure_description\":\"", StructureDescription(G), "\"",
      ",\"is_abelian\":", bool(IsAbelian(G)),
      ",\"is_cyclic\":", bool(IsCyclic(G)),
      ",\"is_nilpotent\":", bool(nilpotent),
      ",\"is_solvable\":", bool(solvable),
      ",\"is_supersolvable\":", bool(IsSupersolvableGroup(G)),
      ",\"is_simple\":", bool(IsSimpleGroup(G)),
      ",\"is_perfect\":", bool(IsPerfectGroup(G)),
      ",\"exponent\":", Exponent(G),
      ",\"num_conjugacy_classes\":", NrConjugacyClasses(G),
      ",\"min_generators\":", Length(generators),
      ",\"center_order\":", Size(Centre(G)),
      ",\"derived_subgroup_order\":", Size(DerivedSubgroup(G)),
      ",\"frattini_order\":", Size(FrattiniSubgroup(G)),
      ",\"abelianization\":", AbelianInvariants(G),
      ",\"automorphism_group_order\":", Size(AutomorphismGroup(G)),
      ",\"derived_length\":", opt(derived_length),
      ",\"nilpotency_class\":", opt(nilpotency_class),
      "}\n");
  od;
od;
QUIT;
"""

TABLES = """
DROP TABLE IF EXISTS small_group;
CREATE TABLE small_group (
    "order" INTEGER NOT NULL,
    "index" INTEGER NOT NULL,
    structure_description TEXT NOT NULL,
    is_abelian INTEGER NOT NULL,
    is_cyclic INTEGER NOT NULL,
    is_nilpotent INTEGER NOT NULL,
    is_solvable INTEGER NOT NULL,
    is_supersolvable INTEGER NOT NULL,
    is_simple INTEGER NOT NULL,
    is_perfect INTEGER NOT NULL,
    exponent INTEGER NOT NULL,
    num_conjugacy_classes INTEGER NOT NULL,
    min_generators INTEGER NOT NULL,
    center_order INTEGER NOT NULL,
    derived_subgroup_order INTEGER NOT NULL,
    frattini_order INTEGER NOT NULL,
    abelianization TEXT NOT NULL,
    automorphism_group_order INTEGER NOT NULL,
    derived_length INTEGER,
    nilpotency_class INTEGER,
    cayley_generators TEXT,
    cayley_graph TEXT,
    PRIMARY KEY ("order", "index"),
    FOREIGN KEY (cayley_graph) REFERENCES graph(graph6));
"""

FIELDS = (
    "structure_description",
    "is_abelian",
    "is_cyclic",
    "is_nilpotent",
    "is_solvable",
    "is_supersolvable",
    "is_simple",
    "is_perfect",
    "exponent",
    "num_conjugacy_classes",
    "min_generators",
    "center_order",
    "derived_subgroup_order",
    "frattini_order",
    "abelianization",
    "automorphism_group_order",
    "derived_length",
    "nilpotency_class",
)


def census(gap: str) -> tuple[str, list[dict[str, Any]]]:
    """GAP's version and one record per group of order up to `MAX_ORDER`."""
    program = GAP_PROGRAM.replace("MAX_ORDER", str(MAX_ORDER))
    result = subprocess.run(
        [gap, "-q", "-b"], input=program, capture_output=True, text=True, check=True
    )
    lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return str(lines[0]["gap_version"]), lines[1:]


def group_row(record: dict[str, Any]) -> tuple[object, ...]:
    return (
        record["order"],
        record["index"],
        *(
            compact(record[field]) if field == "abelianization" else record[field]
            for field in FIELDS
        ),
        None,
        None,
    )


def record_group_provenance(connection: sqlite3.Connection, gap_version: str) -> None:
    """The sources and field provenance of the Group domain."""
    record_sources(
        connection,
        [
            (
                "gap",
                "GAP with the SmallGroups library",
                gap_version,
                "the census of finite groups and their invariants",
                None,
                "The GAP Group, https://www.gap-system.org (GPL)",
            ),
            bridge_mcp_source(),
        ],
    )
    record_provenance(
        connection,
        ["Group"],
        [("Group", "order", "gap", ""), ("Group", "index", "gap", "")]
        + [("Group", field, "gap", "") for field in FIELDS]
        + [
            ("Group", "cayley_generators", "gap", ""),
            ("Group", "cayley_graph", "gap", ""),
            ("Group", "cayley_graph", "bridge-mcp", "Cayley graph construction"),
        ],
    )


def main(gap: str = GAP) -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found; generate the graphs first")
    logging.info("running %s over the groups of order up to %d", gap, MAX_ORDER)
    gap_version, records = census(gap)
    connection = sqlite3.connect(DB_PATH)
    connection.executescript(TABLES)
    connection.executemany(
        f"INSERT INTO small_group VALUES ({', '.join('?' for _ in range(len(FIELDS) + 4))})",
        (group_row(record) for record in records),
    )
    record_group_provenance(connection, gap_version)
    connection.commit()
    connection.close()
    logging.info("wrote %d groups (GAP %s)", len(records), gap_version)
