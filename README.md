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
collections of mathematical objects. A query names the *domains* of objects it ranges over,
gives a *condition* the objects must satisfy, and lists the result columns it
*returns*, each an expression under a column name. It is type-checked and compiled to
SQL, then run against the database that holds the objects. Each row comes back as a
list of column-name/value pairs. Queries are submitted as JSON through the `query`
tool; the output, condition, and ordering are written in a familiar expression syntax —
fields (`g.num_edges`), `id(g)` for an object's primary key, arithmetic, comparisons,
`&&`/`||`/`!`, `defined`/`undefined`, list and tuple literals, and calls to the
functions a database declares. For example, the trees on five vertices:

```json
{
  "domains": [["g", "Graph"]],
  "output": [["graph6", "g.graph6"], ["degree_sequence", "g.degree_sequence"]],
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

The `query` and `describe` tools take a `database` parameter naming the database to
use; calling `describe` with no arguments lists the available databases. Within a
database, the `Source` and `Provenance` domains record which tools and upstream
databases the facts rest on: a provenance row says that trusting its source suffices
for the facts in that field.

### Graphs

The bundled database `math_data` holds every non-isomorphic simple graph on up to 8
vertices (13,598 in all) together with the Cayley graphs of the group census, each
annotated with invariants — the number of vertices and edges, the degree sequence,
connectivity, planarity, and more. The exponential invariants (chromatic number,
clique and independence numbers, automorphism count) are undefined for graphs on more
than 8 vertices. Graphs are stored in canonical graph6 encoding (nauty's `labelg`),
and each graph on up to 8 vertices links to its automorphism group in the census via
`automorphism_group`, when that group has order at most 127. The domain is `Graph`.

### Groups

The same database carries GAP's SmallGroups census of the finite groups of order at
most 127 (1,268 groups) as the `Group` domain, keyed by the GAP id — `Group[24, 12]`
is S4. Each group records its structure description and a selection of invariants
(abelianness, nilpotency and solvability, exponent, center and derived subgroup
orders, abelianization, and more), and every group of order at most 100 links to the
Cayley graph of its minimal generating set via `cayley_graph` — a graph shared with
the `Graph` domain, so graph invariants of Cayley graphs are one join away. Computed
with [GAP](https://www.gap-system.org) (The GAP Group, GPL).

### Topological spaces (π-Base)

The `math_data` database also carries the [π-Base](https://topology.pi-base.org)
community database of topology: domains `Space`, `Property`, and `Theorem`, and a
`Trait` domain holding every space/property value that π-Base asserts *or that is
derivable from its theorems* — 2,115 asserted plus some 50,000 derived traits, each
derived one carrying its provenance (the theorem of its final derivation step and the
premises consumed). Two tools accompany the domains: `search` fuzzy-finds a space,
property, or theorem by name, alias, or statement, and `derivation` unfolds a trait's
full derivation tree down to the asserted facts. The data is © the
[π-Base community](https://github.com/pi-base/data), licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); regenerate the tables from
the current published bundle with `python -m bridge_mcp.generate pibase`.

### Maniplexes

An optional database `sym_ob_small` holds 32,634 regular rank-4 maniplexes together
with their flag graphs, 1-skeleta, 1-coskeleta, and canonical labelings, connected by
foreign keys: a `Maniplex` links to a `CanonicalLabeling`, which links to its `Graph`
(stored in sparse6 encoding), so a query can follow a chain such as
`m.skeleton.graph.sparse6`. The file (≈ 298 MB) is not bundled; download it from
<https://www.andrej.com/tmp/sym-ob-small.db> and save it as
`src/bridge_mcp/mathql/databases/sym-ob-small.db`, where the server picks it up.

## Available tools

### Search and derivation tools

`search` finds π-Base entities and groups by approximate name — `search("hausdorf")`
lands on `$T_2$` through its *Hausdorff* alias, `search("Q8")` on the quaternion
group — returning the uids that MathQL queries need. `derivation` answers "why does
this space have this property": it unfolds the stored provenance of a π-Base trait
into the full derivation tree, each node a theorem application, each leaf a fact
asserted by π-Base.

### Graph tools based on `networkx`

These tools complement the database: where the database records an invariant's *value* (say
the clique number), these tools return a *witness* (an actual maximum clique). They also
build graphs (from an edge list or an adjacency matrix), compare them, and draw them.

This is not the full list — for the complete, current set, list the tools from a running
server (for example with `mcp dev`) or read their docstrings in
`src/bridge_mcp/graph/tools.py`. A few, for flavor: `edge_list`, `invariants`,
`optimal_coloring`, `is_isomorphic`, `draw_graph`.

## Development and contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for information on how to obtain the development version
of the package and how to contribute new databases.
