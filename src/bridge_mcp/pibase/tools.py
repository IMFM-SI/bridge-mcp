"""The `search` and `derivation` tools."""

from __future__ import annotations

import contextlib
import functools
import json
import sqlite3

from mcp.server.fastmcp import FastMCP
from rapidfuzz import fuzz, process, utils

from bridge_mcp.connection import open_read_only, restrict_to_queries
from bridge_mcp.mathql.execute import database_path

INSTRUCTIONS = """## Search and derivation
`search` and `derivation` are the entry points into π-Base. `search` returns the uids a
MathQL query needs; a group's uid is its [order, index] pair."""

KINDS = ("space", "property", "theorem", "group")

Entry = tuple[str, object, str, str]
"""A searchable entry: kind, uid, display name, searched text."""


def _connect() -> sqlite3.Connection:
    connection = open_read_only(database_path())
    restrict_to_queries(connection)
    return connection


@functools.cache
def _catalog() -> tuple[Entry, ...]:
    """Every searchable string: spaces and properties under each of their names,
    theorems under their statements, groups under their structure descriptions."""
    with contextlib.closing(_connect()) as connection:
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
    """Fuzzy-find π-Base spaces, properties, and theorems, and groups, by name.

    text: the name to look for; aliases and near-misses match too.
    kind: restrict to "space", "property", "theorem", or "group" (optional).
    limit: maximum number of results.
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
    """The derivation tree of a trait, unfolded from its stored provenance.

    space, property: π-Base uids, e.g. "S000149" and "P000053"; find them with
    `search`. Each node carries the property and its value, and is either
    asserted or derived by a theorem from premise subtrees.
    """
    with contextlib.closing(_connect()) as connection:
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


def register(mcp: FastMCP) -> None:
    """Register the π-Base tools on `mcp`."""
    for tool in (search, derivation):
        mcp.add_tool(tool)
