"""Checks that the server registers every component's tools and instructions, and
reports an anticipated failure of one with its message."""

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from bridge_mcp.server import mcp


def test_all_tools_registered() -> None:
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {"query", "compile", "describe", "grammar"} <= names
    assert {"edge_list", "neighbors", "shortest_path"} <= names


def test_instructions_compose_components() -> None:
    assert mcp.instructions is not None
    assert "num_vertices" in mcp.instructions  # mathql schema fragment
    assert "Graph tools" in mcp.instructions  # graph component fragment


def test_describe_lists_available_databases() -> None:
    listed = asyncio.run(mcp.call_tool("describe", {})).structured_content
    names = {entry["name"] for entry in listed["databases"]}
    assert "math_data" in names


def test_a_query_error_carries_its_message() -> None:
    request = {"domains": [["g", "Graph"]], "output": [["x", "g.nonesuch"]]}
    with pytest.raises(ToolError, match="domain Graph does not have a field nonesuch"):
        asyncio.run(mcp.call_tool("query", request))


def test_a_malformed_graph6_string_carries_its_message() -> None:
    with pytest.raises(ToolError, match="graph6"):
        asyncio.run(mcp.call_tool("edge_list", {"graph6": "!!!"}))


def test_compile_renders_the_join_a_domain_field_needs() -> None:
    request = {
        "domains": [["g", "Graph"]],
        "output": [["graph6", "id(g)"]],
        "condition": "g.automorphism_group.is_abelian",
    }
    statement = asyncio.run(mcp.call_tool("compile", request)).structured_content["result"]
    assert 'LEFT JOIN "small_group"' in statement
    assert '"aut_group_order"' in statement and '"aut_group_index"' in statement
