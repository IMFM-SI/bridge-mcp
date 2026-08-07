"""The bridge-mcp server: assemble the chosen components into one FastMCP app and run it."""

from __future__ import annotations

import argparse
import sys
from types import ModuleType

from mcp.server.fastmcp import FastMCP

from bridge_mcp.graph import tools as graph_component
from bridge_mcp.instructions import build_instructions
from bridge_mcp.mathql import tools as mathql_component
from bridge_mcp.pibase import tools as pibase_component
from bridge_mcp.sql import tools as sql_component

COMPONENTS: dict[str, ModuleType] = {
    "mathql": mathql_component,
    "pibase": pibase_component,
    "networkx": graph_component,
    "sql": sql_component,
}

DEFAULT = ("mathql", "pibase", "networkx")
"""The components a server runs when the command line names none."""


def build(names: tuple[str, ...] = DEFAULT) -> FastMCP:
    chosen = [COMPONENTS[name] for name in names]
    mcp = FastMCP(
        "bridge-mcp", instructions=build_instructions(c.INSTRUCTIONS for c in chosen)
    )
    for component in chosen:
        component.register(mcp)
    return mcp


mcp = build()


def _components(text: str) -> tuple[str, ...]:
    names = tuple(part.strip() for part in text.split(",") if part.strip())
    unknown = [name for name in names if name not in COMPONENTS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown component {', '.join(unknown)}; known: {', '.join(COMPONENTS)}"
        )
    return names


def main() -> None:
    parser = argparse.ArgumentParser(prog="bridge-mcp", description=__doc__)
    parser.add_argument(
        "--components",
        type=_components,
        default=DEFAULT,
        metavar="NAME,NAME",
        help=f"the components to serve (default: {','.join(DEFAULT)})",
    )
    parser.add_argument(
        "--list-components", action="store_true", help="print the component names and exit"
    )
    arguments = parser.parse_args()
    if arguments.list_components:
        print("\n".join(COMPONENTS))
        sys.exit(0)
    else:
        build(arguments.components).run()


if __name__ == "__main__":
    main()
