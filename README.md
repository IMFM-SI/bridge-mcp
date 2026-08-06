# Bridge MCP

An MCP server for exploring collections of mathematical objects through a simple query language **MathQL**.

## Installation

Install the current version from GitHub:

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
collections of mathematical objects. A query names the *domains* of objects it ranges over,
gives a *condition* the objects must satisfy, and lists the result columns it
*returns*, each an expression under a column name. Each row comes back as a list of
column-name/value pairs. Queries are submitted as JSON through the `query` tool. For
example, the trees on five vertices:

```json
{
  "domains": [["g", "Graph"]],
  "output": [["graph6", "g.graph6"], ["degree_sequence", "g.degree_sequence"]],
  "condition": "g.num_vertices == 5 && g.is_tree"
}
```

Beyond querying, the server offers tools that compute further with the objects a query
finds. A query returns a graph as its `graph6` string, and the graph tools decode and
analyze it. A typical session queries for objects of interest, then inspects them with
these tools.

## Databases

The `query` and `describe` tools take a `database` parameter naming the database to
use; calling `describe` with no arguments lists the available databases. Within a
database, the `Source` and `Provenance` domains record which tools and upstream
databases the facts rest on.

### Graphs

The bundled database `math_data` holds every non-isomorphic simple graph on up to 8
vertices (13,598 in all) together with the Cayley graphs of the group census, each
annotated with invariants. The domain is `Graph`.

### Groups

The same database carries GAP's SmallGroups census of the finite groups of order at
most 127 (1,268 groups) as the `Group` domain, keyed by the GAP id — `Group[24, 12]`
is S4. Computed with [GAP](https://www.gap-system.org) (The GAP Group, GPL).

### Topological spaces (π-Base)

The `math_data` database also carries the [π-Base](https://topology.pi-base.org)
community database of topology: domains `Space`, `Property`, `Theorem` and `Trait`,
holding 2,114 asserted plus some 50,000 derived traits. The data is © the
[π-Base community](https://github.com/pi-base/data), licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and is a snapshot of a
published bundle.

### Maniplexes

An optional database `sym_ob_small` holds regular rank-4 maniplexes and the graphs
derived from them. The file (≈ 298 MB) ships separately; download it from
<https://www.andrej.com/tmp/sym-ob-small.db> and save it as
`src/bridge_mcp/mathql/databases/sym-ob-small.db`, where the server picks it up.

## Available tools

Besides `query`, `describe` and `grammar`, the server offers `search` and `derivation`
into π-Base, and graph tools built on `networkx`. Where the database records an
invariant's *value*, such as the clique number, a graph tool returns a *witness*, an
actual maximum clique. Each tool carries its own description; a running server lists
them all.

## Development and contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for information on how to obtain the development version
of the package and how to contribute new databases.
