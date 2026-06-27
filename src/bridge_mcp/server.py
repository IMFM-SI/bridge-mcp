"""The bridge-mcp server: assemble the components into one FastMCP app and run it."""

from mcp.server.fastmcp import FastMCP

from bridge_mcp import graph, mathql
from bridge_mcp.instructions import build_instructions

COMPONENTS = (mathql, graph)


def build() -> FastMCP:
    mcp = FastMCP(
        "bridge-mcp", instructions=build_instructions(c.INSTRUCTIONS for c in COMPONENTS)
    )
    for component in COMPONENTS:
        component.register(mcp)
    return mcp


mcp = build()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
