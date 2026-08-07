"""The mathql component: the `query`, `describe`, and `grammar` tools over the databases."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from bridge_mcp.databases import DATABASES, Open
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.execute import run_query

_SUMMARY = """## Writing queries
Expressions use fields (g.num_vertices), id(x) for an object's primary key, literals,
arithmetic (+ - *), comparisons (== != < <= > >=), booleans (&& || !), defined/undefined
for absence, list and tuple literals ([1, 2] and (1, 'a'), a tuple projected with .0),
and calls to the functions a database declares (f(x, y)). A comparison needs both sides
the same type. Call the `grammar` tool for the full grammar."""


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
        f"parameter selecting one (default: {default}).",
        "",
    ]
    for name, opened in DATABASES.items():
        lines += _database_section(name, opened.database.describe()) + [""]
    lines.append(_SUMMARY)
    return "\n".join(lines)


INSTRUCTIONS = _build_instructions()


def register(mcp: FastMCP) -> None:
    """Register the query tools on `mcp`."""

    default = next(iter(DATABASES), None)

    def resolve(database: str | None) -> Open:
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
        postprocess: list[tuple[str, str]] | None = None,
        database: str | None = None,
    ) -> list[list[tuple[str, Any]]]:
        """Run a MathQL query and return the matching rows, each a list of
        [column name, value] pairs, in the order `output` then `postprocess` name them.

        A query ranges over one object per domain variable and returns one row per
        combination the condition holds of. The `grammar` tool gives the expression
        grammar with its precedence, the types, and the full result shape.

        domains: the variable bindings the query ranges over, e.g. [["g", "Graph"]].
        output: [column name, expression] pairs, in the order the columns are to
            appear, e.g. [["g6", "id(g)"], ["edges", "g.num_edges"]].
        condition: a boolean expression; a row appears when it holds.
        order: [expression, "asc"|"desc"] pairs sorting the rows, applied in turn.
        limit: how many rows to return at most.
        postprocess: [column name, expression] pairs computed per row after the database
            answers; each may name an output column and the entries before it.
        database: which database to query (optional; the default is the first).
        """
        opened = resolve(database)
        request: dict[str, Any] = {"domains": domains, "output": output}
        if condition is not None:
            request["condition"] = condition
        if order is not None:
            request["order"] = order
        if limit is not None:
            request["limit"] = limit
        if postprocess is not None:
            request["postprocess"] = postprocess
        try:
            return run_query(opened.connection, opened.database, opened.is_safe_alias, request)
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
                    {"name": name, "overview": opened.database.overview}
                    for name, opened in DATABASES.items()
                ]
            }
        else:
            return resolve(database).database.describe()

    @mcp.tool()
    def grammar() -> str:
        """The full query-language grammar: the query shape, the result shape, the
        domains, the types, and the expression grammar with precedence."""
        return (
            resources.files("bridge_mcp.mathql")
            .joinpath("query-grammar.md")
            .read_text(encoding="utf-8")
        )
