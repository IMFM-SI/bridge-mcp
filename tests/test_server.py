"""Checks that the server registers every component's tools and instructions."""

import asyncio

from bridge_mcp.server import mcp


def test_all_tools_registered() -> None:
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {"query", "describe", "grammar"} <= names
    assert {"edge_list", "neighbors", "shortest_path"} <= names


def test_instructions_compose_components() -> None:
    assert mcp.instructions is not None
    assert "num_vertices" in mcp.instructions  # mathql schema fragment
    assert "Graph tools" in mcp.instructions  # graph component fragment


def test_describe_lists_available_databases() -> None:
    listed = asyncio.run(mcp.call_tool("describe", {})).structured_content
    names = {entry["name"] for entry in listed["databases"]}
    assert "math_data" in names
