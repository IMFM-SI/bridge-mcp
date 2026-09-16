"""The `search` and `derivation` tools."""

from __future__ import annotations

import functools
import json

from mcp.server.mcpserver import MCPServer
from rapidfuzz import fuzz, process, utils

from bridge_mcp.databases import resolve

INSTRUCTIONS = """## Search and derivation
π-Base records traits. A trait is a space, a property, and a boolean value recording
whether the space has the property. A trait is asserted, or a theorem derives it from
other traits. A space's uid reads `S000149`, a property's `P000053`, a theorem's
`T000264`; a group's uid is its `[order, index]` pair.

`search` matches text against the names and aliases of spaces and properties, the
statements of theorems, and the structure descriptions of groups, and returns the uid of
each match. `derivation` returns the tree of traits and theorems beneath one trait. The
`Space`, `Property`, `Theorem`, `Trait` and `Group` domains hold the same objects for
`query`.

Examples:
- `search("long line")` returns the spaces whose names match, in descending score.
- `search("compact", kind="property")` returns the matching properties alone.
- `search("dihedral", kind="group")` returns groups by structure description.
- `derivation("S000149", "P000053")` returns the tree beneath the trait of the space
  "Two-sided long line" and the property "Metrizable"."""

KINDS = ("space", "property", "theorem", "group")

Entry = tuple[str, object, str, str]
"""A searchable entry: kind, uid, display name, searched text."""


@functools.cache
def _catalog() -> tuple[Entry, ...]:
    """Every searchable string: spaces and properties under each of their names,
    theorems under their statements, groups under their structure descriptions."""
    connection = resolve("math_data").connection
    named = [
        (kind, row)
        for kind, table in (("space", "pibase_space"), ("property", "pibase_property"))
        for row in connection.execute(f"SELECT uid, name, aliases FROM {table}")
    ]
    theorems = connection.execute("SELECT uid, statement FROM pibase_theorem").fetchall()
    groups = connection.execute(
        'SELECT "order", "index", structure_description FROM small_group'
    ).fetchall()
    return tuple(
        [
            (kind, uid, name, text)
            for kind, (uid, name, aliases) in named
            for text in [name, *json.loads(aliases)]
        ]
        + [("theorem", uid, statement, statement) for uid, statement in theorems]
        + [("group", [order, index], name, name) for order, index, name in groups]
    )


def search(text: str, kind: str | None = None, limit: int = 10) -> list[dict[str, object]]:
    """Match text against the names and aliases of π-Base spaces and properties, the
    statements of theorems, and the structure descriptions of groups.

    Each result is {"kind": "space", "property", "theorem" or "group"; "uid": the object's
    uid, which for a group is its [order, index] pair; "name": the space's or property's
    name, the theorem's statement, or the group's structure description; "score": the
    match, from 0 to 100}. The results come in descending score, one per object.

    text: the text to match; a near spelling matches too.
    kind: restrict the results to one kind.
    limit: how many results to return.
    """
    if kind is not None and kind not in KINDS:
        raise ValueError(f"unknown kind '{kind}'; expected one of {', '.join(KINDS)}")
    entries = [entry for entry in _catalog() if kind is None or entry[0] == kind]
    hits = process.extract(
        text,
        [searched for _, _, _, searched in entries],
        scorer=fuzz.WRatio,
        processor=utils.default_process,
        limit=None,
    )
    results: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for _, score, index in hits:
        entry_kind, uid, name, _ = entries[index]
        if (entry_kind, repr(uid)) not in seen:
            seen.add((entry_kind, repr(uid)))
            results.append(
                {"kind": entry_kind, "uid": uid, "name": name, "score": round(score)}
            )
        if len(results) == limit:
            break
    return results


def derivation(space: str, property: str) -> dict[str, object]:
    """The tree of traits and theorems beneath one trait of π-Base.

    A trait is a space, a property, and a boolean value recording whether the space has
    the property. The result is {"space": the space's name, "uid": the space's uid,
    "trait": the root node}. A node is {"property": the property's name, "uid": the
    property's uid, "value": the boolean} together with either {"asserted": true} or
    {"theorem": the theorem's uid, "statement": what the theorem says, "premises": the
    list of nodes the theorem drew on}:

        {"space": "Two-sided long line", "uid": "S000149",
         "trait": {"property": "Metrizable", "uid": "P000053", "value": false,
                   "theorem": "T000264", "statement": "Metrizable ⇒ Pseudometrizable",
                   "premises": [{"property": "Pseudometrizable", "uid": "P000121",
                                 "value": false, "theorem": "T000268", ...}]}}

    space: a space uid, "S000149"; `search` returns them.
    property: a property uid, "P000053".
    """
    connection = resolve("math_data").connection
    names = dict(connection.execute("SELECT uid, name FROM pibase_property"))
    statements = dict(connection.execute("SELECT uid, statement FROM pibase_theorem"))
    named = connection.execute(
        "SELECT name FROM pibase_space WHERE uid = ?", (space,)
    ).fetchone()
    if named is None:
        raise ValueError(f"unknown space '{space}'")

    def node(prop: str) -> dict[str, object]:
        row = connection.execute(
            "SELECT value, asserted, theorem, premises FROM pibase_trait"
            " WHERE space = ? AND property = ?",
            (space, prop),
        ).fetchone()
        if row is None:
            raise ValueError(f"no known trait for {space} and {prop}")
        value, asserted, theorem, premises = row
        base: dict[str, object] = {
            "property": names[prop],
            "uid": prop,
            "value": bool(value),
        }
        if asserted:
            return base | {"asserted": True}
        else:
            return base | {
                "theorem": theorem,
                "statement": statements[theorem],
                "premises": [node(premise) for premise, _ in json.loads(premises)],
            }

    return {"space": named[0], "uid": space, "trait": node(property)}


def register(mcp: MCPServer) -> None:
    """Register the π-Base tools on `mcp`."""
    for tool in (search, derivation):
        mcp.add_tool(tool)
