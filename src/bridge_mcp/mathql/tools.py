"""The mathql component: the `query`, `describe`, and `grammar` tools over a database."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from importlib import resources
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.mathql.databases.small_graphs import database
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import database_path, run_query

_SUMMARY = """## Writing queries
`query` takes domains (e.g. [["g", "Graph"]]); output (["g.field", ...], or ["g"] for the
whole object); and optional condition, order ([expression, "asc"|"desc"] pairs), and
limit. Conditions and order expressions use fields (g.num_vertices), literals, arithmetic
(+ - *), comparisons (== != < <= > >=), booleans (&& || !), defined/undefined for absence,
and list/tuple literals. ASCII operators are preferred; ∧ ∨ ¬ ≤ ≥ ≠ also work. Call the
`grammar` tool for the full grammar."""


def _build_instructions(schema: dict[str, Any]) -> str:
    lines = [schema["overview"], "", "## Domains and fields"]
    for domain in schema["domains"]:
        lines.append(f"- {domain['name']}: {domain['doc']}")
        for field in domain["fields"]:
            lines.append(f"    {field['label']} : {field['type']} — {field['doc']}")
    lines += ["", _SUMMARY, "", "## Examples (call `describe` for the full list)"]
    for example in schema["examples"][:3]:
        lines.append(f"- {example['note']}: {json.dumps(example['query'])}")
    return "\n".join(lines)


INSTRUCTIONS = _build_instructions(database.describe())


def register(mcp: FastMCP) -> None:
    """Register the query tools on `mcp`."""

    @mcp.tool()
    def query(
        domains: list[list[str]],
        output: list[str],
        condition: str | None = None,
        order: list[list[str]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Run a MathQL query and return the matching rows.

        domains: variable bindings, e.g. [["g", "Graph"]].
        output: items to return, each "x" (the whole object) or "x.field".
        condition: a boolean expression over the bound variables (optional).
        order: [expression, "asc"|"desc"] pairs (optional).
        limit: maximum number of rows (optional).
        """
        request: dict[str, Any] = {"domains": domains, "output": output}
        if condition is not None:
            request["condition"] = condition
        if order is not None:
            request["order"] = order
        if limit is not None:
            request["limit"] = limit
        try:
            with contextlib.closing(sqlite3.connect(database_path())) as connection:
                return run_query(connection, database, request)
        except MathQLError as error:
            raise ValueError(str(error)) from error

    @mcp.tool()
    def describe() -> dict[str, object]:
        """Return the database schema: domains, fields, constants, and examples."""
        return database.describe()

    @mcp.tool()
    def grammar() -> str:
        """The full query-language grammar: the JSON query shape, the types, the
        expression grammar with precedence, and examples."""
        return (
            resources.files("bridge_mcp.mathql")
            .joinpath("query-grammar.md")
            .read_text(encoding="utf-8")
        )
