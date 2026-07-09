"""The mathql component: the `query`, `describe`, and `grammar` tools over the databases."""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.databases import math_data, sym_ob_small
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import database_path, run_query


def _sym_ob_path() -> Path | None:
    """The maniplex database's path from `BRIDGE_MCP_SYM_OB_DB`, if set."""
    value = os.environ.get("BRIDGE_MCP_SYM_OB_DB")
    if value is None:
        return None
    else:
        return Path(value)


def _candidates() -> tuple[tuple[str, Database, Path | None, str], ...]:
    """The known databases: name, schema, file path if determined, and how to enable."""
    return (
        ("math_data", math_data.database, database_path(), "bundled with the package"),
        (
            "sym_ob_small",
            sym_ob_small.database,
            _sym_ob_path(),
            "download https://www.andrej.com/tmp/sym-ob-small.db and point the "
            "BRIDGE_MCP_SYM_OB_DB environment variable at it",
        ),
    )


CANDIDATES = _candidates()

DATABASES = {
    name: (database, path)
    for name, database, path, _ in CANDIDATES
    if path is not None and path.exists()
}

_SUMMARY = """## Writing queries
`query` takes: domains (e.g. [["g", "Graph8"]]); output, a mapping from each result
column name to the expression it returns (e.g. {"g6": "id(g)", "edges": "g.num_edges"});
and optional condition, order ([expression, "asc"|"desc"] pairs, which may refer to the
output column names), limit, and database. Expressions use fields (g.num_vertices),
id(x) for an object's primary key, literals, arithmetic (+ - *), comparisons
(== != < <= > >=), booleans (&& || !), and defined/undefined for absence; a comparison
needs both sides the same type. String literals are single-quoted ('text', a literal
quote doubled as ''). ASCII operators are preferred; ∧ ∨ ¬ ≤ ≥ ≠ also work. Call the
`grammar` tool for the full grammar."""


def _database_section(name: str, schema: dict[str, Any]) -> list[str]:
    """The instruction lines for one database: overview, domains, two examples."""
    lines = [f"## Database `{name}`", schema["overview"], "", "### Domains and fields"]
    for domain in schema["domains"]:
        lines.append(f"- {domain['name']}: {domain['doc']}")
        if domain["inputFields"]:
            lines.append("  Input fields — scalar values, written `x.field`:")
            for field in domain["inputFields"]:
                lines.append(f"    {field['label']} : {field['type']} — {field['doc']}")
        if domain["domainFields"]:
            lines.append(
                "  Domain fields — links to another object, written `x.field`, yielding "
                "an object you can project or take id() of:"
            )
            for field in domain["domainFields"]:
                lines.append(f"    {field['label']} → {field['domain']} — {field['doc']}")
    lines += ["", "### Examples (call `describe` for the full list)"]
    for example in schema["examples"][:2]:
        lines.append(f"- {example['note']}: {json.dumps(example['query'])}")
    return lines


def _build_instructions() -> str:
    default = next(iter(DATABASES), "")
    lines = [
        f"Databases: {', '.join(name for name, *_ in CANDIDATES)}. `query` and "
        f"`describe` take a `database` parameter selecting one (default: {default}); "
        "`describe` with no arguments lists them.",
        "",
    ]
    for name, selected, _, hint in CANDIDATES:
        if name in DATABASES:
            lines += _database_section(name, selected.describe()) + [""]
        else:
            lines += [
                f"## Database `{name}` (not available)",
                selected.overview,
                f"To enable: {hint}.",
                "",
            ]
    lines.append(_SUMMARY)
    return "\n".join(lines)


INSTRUCTIONS = _build_instructions()


def _listing_entry(name: str, selected: Database, hint: str) -> dict[str, object]:
    """One entry of the database listing: unavailable databases say how to enable."""
    if name in DATABASES:
        return {"name": name, "overview": selected.overview, "available": True}
    else:
        return {
            "name": name,
            "overview": selected.overview,
            "available": False,
            "enable": hint,
        }


def register(mcp: FastMCP) -> None:
    """Register the query tools on `mcp`."""

    default = next(iter(DATABASES), None)

    def resolve(database: str | None) -> tuple[Database, Path]:
        name = database if database is not None else default
        if name is not None and name in DATABASES:
            return DATABASES[name]
        else:
            raise ValueError(f"unknown database '{name}'; available: {', '.join(DATABASES)}")

    @mcp.tool()
    def query(
        domains: list[list[str]],
        output: dict[str, str],
        condition: str | None = None,
        order: list[list[str]] | None = None,
        limit: int | None = None,
        database: str | None = None,
    ) -> list[dict[str, object]]:
        """Run a MathQL query and return the matching rows.

        domains: variable bindings, e.g. [["g", "Graph8"]].
        output: a mapping from result column name to the expression it returns,
            e.g. {"g6": "id(g)", "edges": "g.num_edges"}.
        condition: a boolean expression over the bound variables (optional).
        order: [expression, "asc"|"desc"] pairs; the expressions may refer to the
            output column names (optional).
        limit: maximum number of rows (optional).
        database: which database to query (optional; call `describe` with no
            arguments for the list, the first entry being the default).
        """
        selected, path = resolve(database)
        request: dict[str, Any] = {"domains": domains, "output": output}
        if condition is not None:
            request["condition"] = condition
        if order is not None:
            request["order"] = order
        if limit is not None:
            request["limit"] = limit
        try:
            with contextlib.closing(
                sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            ) as connection:
                return run_query(connection, selected, request)
        except MathQLError as error:
            raise ValueError(str(error)) from error

    @mcp.tool()
    def describe(database: str | None = None) -> dict[str, object]:
        """Describe a database: its domains, fields, constants, and examples.

        With no `database`, list the available databases and their overviews.
        """
        if database is None:
            return {
                "databases": [_listing_entry(name, s, hint) for name, s, _, hint in CANDIDATES]
            }
        else:
            selected, _ = resolve(database)
            return selected.describe()

    @mcp.tool()
    def grammar() -> str:
        """The full query-language grammar: the JSON query shape, the types, the
        expression grammar with precedence, and examples."""
        return (
            resources.files("bridge_mcp.mathql")
            .joinpath("query-grammar.md")
            .read_text(encoding="utf-8")
        )
