"""The bridge-mcp server: assemble the components into one FastMCP app and run it."""

from mcp.server.fastmcp import FastMCP

from bridge_mcp.graph import tools as graph_component
from bridge_mcp.instructions import build_instructions
from bridge_mcp.mathql import tools as mathql_component

COMPONENTS = (mathql_component, graph_component)


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
