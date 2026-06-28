# Bridge MCP

An MCP server for exploring collections of mathematical objects through a simple query language **MathQL**.

## Installation

`bridge-mcp` is not yet published on PyPI; install the current version directly from
GitHub:

    pip install git+https://github.com/IMFM-SI/bridge-mcp.git

This installs the `bridge-mcp` command together with a small bundled database of mathematical
objects, so the server is ready to run with no further setup. Register `bridge-mcp` as a command
with your MCP client.

## Use with Claude Desktop

To add the MCP Bridge to Claude Desktop you need to edit its JSON configuration file:

* **MacOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`,
* **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Under `mcpServers` section you add the following stanza:

```json
{
  "mcpServers": {
    "bridge-mcp": { "command": "⟨absolute-path⟩/bridge-mcp" }
  }
}
```

where `⟨absolute-path⟩` depends on where the `bridge-mcp` command has been installed:

1. If you installed Bridge MCP with `pip` then `which bridge-mcp` should tell you the
   absolute path to the executable.

2. If you cloned the repository and would like to test the development version installed
   therein, the absolute path takes the form `⟨absolute-path-to-bridge-mcp-repository⟩/.venv/bin/bridge-mcp`.

You need to restart Claude Desktop for the setting to take effect.

## MathQL

MathQL is a small, typed query language for asking mathematical questions about
collections of mathematical objects. A query names one or more *domains* of objects,
gives a *condition* the objects must satisfy, and lists what to *return*. It is
type-checked and compiled to SQL, then run against the database that holds the objects.
Queries are submitted as JSON through the `query` tool; conditions and ordering are
written in a familiar expression syntax — arithmetic, comparisons, `&&`/`||`/`!`,
`defined`/`undefined`, and list and tuple literals. For example, the trees on five
vertices:

```json
{
  "domains": [["g", "Graph8"]],
  "output": ["g.graph6", "g.degree_sequence"],
  "condition": "g.num_vertices == 5 && g.is_tree"
}
```

Beyond querying, the server offers tools that compute further with the objects a query
finds. A graph comes back as its `graph6` string, a compact encoding that is opaque on
its own; passing that string to the `edge_list` tool returns the graph's vertices and
edges, and other tools give neighbors, shortest paths, a maximum clique, a proper
coloring, and more. A typical session queries for objects of interest, then inspects
them with these tools.

## Databases

### Small graphs

The database holds every non-isomorphic simple graph on up to 8 vertices
(13,598 in all), each annotated with a selection of invariants: order and size, the
degree sequence, connectivity and number of components, diameter, radius, girth,
planarity, bipartiteness, the chromatic number, the clique and independence numbers, the
number of triangles, and the order of the automorphism group. Every invariant is both
queryable in a condition and returnable in the output; the graph itself is stored in
graph6 encoding. The single domain is `Graph8` — call the `describe` tool for the full
field list. The database is generated with nauty and networkx
(see `scripts/generate_graphs.py`).

## Available tools

### Graph tools based on `networkx`

These tools complement the database: where the database records an invariant's *value* (say the
clique number), these tools return a *witness* (an actual maximum clique). The available tools
include:

- `edge_list` — the vertex count and the list of edges;
- `neighbors`, `shortest_path` — a vertex's neighbors, a shortest path between two vertices;
- `max_clique`, `max_independent_set`, `connected_components` — witnesses for the clique
  number, independence number, and component count;
- `coloring` — a proper vertex coloring.

See the tool docstrings in `src/bridge_mcp/graph/tools.py`, or list the tools from a
running server (for example with `mcp dev`), for their complete and up-to-date
descriptions.

## Development and contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for information on how to obtain the development version
of the package and how to contribute new databases.
