# Handoff: the mcp 2 port

The work is on `main`: five commits on top of `0358663`, followed by the commit adding this
file. Remote is `git@github.com:IMFM-SI/bridge-mcp.git`.

This repository and `../bridge-query-language` are developed in tandem. They hold two
implementations of one language, MathQL: in Lean there, in Python here. This repository is
what ships as the MCP server. See *How the two repositories relate* below, and
`../bridge-query-language/HANDOFF.md` for that side.

## State

Verified on 2026-10-09 in `.venv` (Python 3.14.3, mcp 2.2.0):

- `pytest -q` — 239 passed, 4 skipped.
- `mypy src` — clean, 44 files.
- `ruff format --check .` — clean, 75 files.
- `ruff check .` — **31 findings, all of them present at `0358663` too**, before this work.
  They are `LOG015`, `ISC004`, `DTZ011`, `BLE001`, `EXE001` in `generate/` and `scripts/`,
  plus two `I001` import-sort findings. CI runs `ruff check .` and so failed before this
  work as well.

The 4 skips are `tests/test_sym_ob.py`: `sym-ob-small.db` is not present. It is a ≈ 298 MB
download, see `README.md`.

## What the five commits did

- **`3fea3b9` Serve the mcp 2 SDK.** `pyproject.toml` carried `mcp[cli]` with no upper
  bound, so any install made after mcp 2.0's release resolves to 2.x, where
  `mcp.server.fastmcp` raises `ModuleNotFoundError` and the server does not start. Bound to
  `>=2,<3`; `FastMCP` → `MCPServer` in five modules; `check_same_thread=False` in
  `open_read_only`; the two tests that read `call_tool`'s result.
- **`d7b69af` Take every connection from the databases the server opened.** `search` and
  `derivation` opened their own connection on `math-data.db`, `derivation` once per call.
  Both now read `databases.resolve("math_data").connection`.
- **`4f4b070` Report each anticipated failure with its message.** See *The error rule*.
- **`e069395` Return the SQL a query compiles to.** The `compile` tool.
- **`9e7a499` Add division to the arithmetic.** `/` in MathQL.

## Facts that are not in the repository

### The three mcp 2 breakages

Only the first is visible as an import error; the other two surface when a tool runs. All
three are stated in <https://py.sdk.modelcontextprotocol.io/v2/migration/>, which is the
document to read before touching the SDK surface again.

1. `FastMCP` is `mcp.server.mcpserver.MCPServer`. Its constructor's **positional** order
   changed to `name, title, description, instructions, website_url, icons, version`;
   `server.py` passes `instructions` by keyword and is unaffected.
2. A synchronous handler runs in a worker thread via `anyio.to_thread.run_sync()`. The
   connections in `databases.DATABASES` are opened at import time on the main thread.
   `sqlite3.threadsafety` is 3 and SQLite reports `THREADSAFE=1`, its serialized mode, so
   `check_same_thread=False` is sound; read-only mode, the attached-database limit and the
   authorizer are properties of the connection, not of the thread. The SDK's own
   alternative is to declare a handler `async def`, which would mean changing about thirty
   signatures and blocking the event loop per query.
3. `MCPServer.call_tool()` returns a `CallToolResult` — read `.content` and
   `.structured_content` — and **raises** `ToolError`; the `is_error=True` result is built
   one layer up, in `_handle_call_tool`. Model fields are snake_case now (`is_error`,
   `input_schema`); the wire format is unchanged.

### The error rule

From the migration guide: `ToolError` for a tool execution failure the calling model should
see and react to, `MCPError` for a request the server rejects outright. Every failure
`bridge-mcp` has originates in the tool and is one the agent can correct, so **every one is
a `ToolError` and `MCPError` appears nowhere.**

`failure.anticipating(*kinds)` wraps a tool so a failure of those kinds raises `ToolError`
with its message; anything else stays a crash, whose traceback the SDK logs and whose
message it withholds. Each component names its own kinds where it registers:

- graph — `ValueError`, `networkx.NetworkXException`
- mathql — `MathQLError`, `ValueError`
- sql — `sqlite3.Error`, `ValueError`
- pibase — `ValueError`

This covers the networkx failures (a malformed `graph6` string, a vertex outside the graph)
which have no deliberate raise anywhere and which no per-site edit would have reached.

**`src/bridge_mcp/generate/` must not import the MCP SDK** — it runs outside any server.
It imports `pibase.deduction` and `graph.invariants` and nothing else from the package, so
neither of those may import the SDK either. `pibase/deduction.py` is reached only by the
generator, never by a tool.

### Division semantics

`/` must mean what SQLite's `/` means, because the condition, output and order clauses
reach the database as SQL and only `postprocess` is evaluated in Python. Two places where
Python does not agree, both handled in `execute._quotient`:

- SQLite truncates toward zero; Python's `//` floors. `-7 / 2` is `-3`, not `-4`.
- SQLite yields `NULL` on a zero divisor. `_quotient` raises `MathQLError`, which the
  postprocess evaluator already turns into the same absent value, so `undefined (n / 0)` is
  true on both paths.

`tests/test_execute.py` runs each sign combination through both stages on one row.

### Driving the server

`bridge-mcp` is **not** connected as an MCP tool in a Claude Code session. To exercise it,
drive it as a client over stdio:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
params = StdioServerParameters(command=".venv/bin/bridge-mcp",
                               args=["--components", "mathql,pibase,networkx,sql"])
```

`describe` gives the schema; do not read the database descriptors to answer schema
questions. The compiled SQL is **not** reachable through any tool other than `compile`.

### The slide example

Constructed for a demonstration of MathQL against its compiled SQL. The join comes from the
condition alone, so the `SELECT` list does not reveal why it is there.

```json
{"domains": [["g", "Graph"]],
 "output": [["graph6", "id(g)"], ["chromatic_number", "g.chromatic_number"]],
 "condition": "g.is_regular && g.max_degree == 3 && g.automorphism_group.is_abelian"}
```

```sql
SELECT c1."graph6" AS c2, c1."chromatic_number" AS c3
FROM "graph" AS c1
LEFT JOIN "small_group" AS c4
  ON c4."order" = c1."aut_group_order" AND c4."index" = c1."aut_group_index"
WHERE ((c1."is_regular" AND (c1."max_degree" = 3)) AND c4."is_abelian")
```

One row: `GtPHOk`, chromatic number 3 — the least symmetric of the five connected cubic
graphs on 8 vertices, `|Aut| = 4`. The join is `LEFT` because `automorphism_group` is
undefined above order 127 or 8 vertices; an inner join would drop those rows rather than
leave the field absent.

Database contents: 14,281 graphs (13,598 on up to 8 vertices, 683 Cayley), 1,268 groups of
order ≤ 127, and π-Base with 223 spaces, 246 properties, 926 theorems, 52,330 traits of
which 2,114 asserted.

## How the two repositories relate

This is a decision, made on 2026-10-09.

- The design of MathQL is done in Lean. Its concrete syntax, abstract syntax and
  type-checking are defined in `bridge-query-language`: in `LANGUAGE.md` and in the Lean
  implementation under `MathQL/`. The Python implementation in `bridge-mcp` follows them.
- Incidental functionality may differ between the two implementations. Extra
  database-declared functions are the standing example. The MCP tools of `bridge-mcp`,
  such as `compile`, are not part of the language at all.
- The boundary between design and incidental functionality is not drawn more precisely
  than this. When a change could fall on either side, ask.

Commit `9e7a499` in `bridge-mcp` added the division operator `/` to Python first, which is
the wrong order under this rule. The decision is that Lean catches up; the operator stays
in Python.

## Work to be done

These are decided. Each is to be done.

1. **Add the division operator to the Lean implementation and to `LANGUAGE.md`.** Specified
   in `../bridge-query-language/HANDOFF.md`, with two cautions about Lean's integer
   division.
2. **Fix the encoding of booleans nested in JSON.** Under the rule above the fix is
   designed in Lean first; `../bridge-query-language/HANDOFF.md` carries it, with the
   evidence. The Python implementation needs the same fix after. In short: a boolean
   inside a tuple or a list comes back as `1` or `0` instead of `true` or `false`.

## A plan mentioned but not recorded

On 2026-10-09 the user recalled a plan to let MathQL queries refer directly to Python
functions. Neither repository and no saved session transcript records it. Ask the user
what it is before acting on it.

The nearest existing mechanism is the *postprocess function*: a function implemented in
the host language, declared by a database, and callable by name from the `postprocess`
clause alone, since the other clauses run in SQLite. In Python it is `PostFunction` in
`bridge-mcp/src/bridge_mcp/mathql/database.py`; in Lean, `postFunction` in
`MathQL/MathQL/Database.lean`. No real database declares one. The only one is `plus`, in the
test databases of both repositories.

## Facts the next session will meet

Nothing has been decided about these. They are recorded so they do not surprise anyone.

- `ruff check .` reports 31 findings, the same 31 it reported at `0358663` before this work,
  so continuous integration's lint step fails on `main` too.
- The maniplex database `sym-ob-small.db` is absent, so `tests/test_sym_ob.py` is skipped.

## Working agreements for whoever continues

- Do not install anything. Show the command and stop.
- A question is a question. Answer it; do not edit.
- Propose one step, then wait. Do not dump a multi-file plan.
- Fix design warts found along the way rather than scoping them out, but say what you are
  about to do first.
- Commit messages: imperative summary, a body stating what is the case and what was
  checked. No history, no rejected alternatives. The same goes for comments and docstrings.
