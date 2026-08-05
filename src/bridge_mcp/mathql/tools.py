"""The mathql component: the `query`, `describe`, and `grammar` tools over the databases."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from bridge_mcp.mathql.database import Database
from bridge_mcp.mathql.databases import math_data, sym_ob_small
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import database_path, run_query


def _available() -> dict[str, tuple[Database, Path]]:
    """The databases whose files are present, keyed by name."""
    candidates = (
        ("math_data", math_data.database, database_path()),
        ("sym_ob_small", sym_ob_small.database, sym_ob_small.database_path()),
    )
    return {name: (database, path) for name, database, path in candidates if path.exists()}


DATABASES = _available()

_SUMMARY = """## Writing queries
`query` takes: domains (e.g. [["g", "Graph"]]); output, a list of [column name,
expression] pairs in the order the columns are to appear (e.g. [["g6", "id(g)"],
["edges", "g.num_edges"]]); and optional condition, order ([expression, "asc"|"desc"]
pairs, which may refer to the output column names), limit, and database. Each returned
row is a list of [column name, value] pairs in that same order. Expressions use fields
(g.num_vertices),
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
        f"Databases: {', '.join(DATABASES)}. `query` and `describe` take a `database` "
        f"parameter selecting one (default: {default}); `describe` with no arguments "
        "lists them.",
        "",
    ]
    for name, (selected, _) in DATABASES.items():
        lines += _database_section(name, selected.describe()) + [""]
    lines.append(_SUMMARY)
    return "\n".join(lines)


INSTRUCTIONS = _build_instructions()


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
        domains: list[tuple[str, str]],
        output: list[tuple[str, str]],
        condition: str | None = None,
        order: list[tuple[str, Literal["asc", "desc"]]] | None = None,
        limit: int | None = None,
        database: str | None = None,
    ) -> list[list[tuple[str, Any]]]:
        """Run a MathQL query and return the matching rows.

        Each row is a list of [column name, value] pairs, the output columns in
        their given order.

        domains: variable bindings, e.g. [["g", "Graph"]].
        output: [column name, expression] pairs, in the order the columns are to
            appear, e.g. [["g6", "id(g)"], ["edges", "g.num_edges"]]. Each
            expression is over the bound variables (see the grammar tool).
        condition: a boolean expression over the bound variables (optional).
        order: [expression, "asc"|"desc"] pairs; the expressions may refer to the
            output column names (optional).
        limit: maximum number of rows (optional).
        database: which database to query (optional; `describe` with an empty
            argument list returns the list, the first entry being the default).
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
                "databases": [
                    {"name": name, "overview": selected.overview}
                    for name, (selected, _) in DATABASES.items()
                ]
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
