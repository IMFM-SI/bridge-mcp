# Callback functions

We are trying to implement a way to call selected Python functions mid-query, so the function can be evaluated on the elements of the SQLite database.



## Signature
In `mathql/database.py` there exist signatures for `SqlFunction` and `PostFunction`.
I propose a similar signature to `PostFunction`:
```py
@dataclass(frozen=True)
class PostFunction:
    """A function callable in the postprocess clause: its MathQL name, its signature, and
    an implementation over the decoded argument values, raising `MathQLError` on an
    argument it rejects."""

    name: str
    arg_types: tuple[Ty, ...]
    result_ty: Ty
    implementation: Callable[[Sequence[object]], object]

    def signature(self) -> Signature:
        return Signature(self.arg_types, self.result_ty)
```
I would add `sql_name` so the names of the native SQLite functions (`abs`, `length`, ...) don't get mixed up with Python functions. Each Python function gets the `mathql_` prefix, through a `@property` called `sql_name`:
```py
@dataclass(frozen=True)
class CallbackFunction:
    """A Python function a query can call while SQLite reads the rows: its MathQL name,
    its signature, an implementation over the decoded argument values, and a human
    description. SQLite knows it as `mathql_` followed by its name."""

    name: str
    arg_types: tuple[Ty, ...]
    result_ty: Ty
    implementation: Callable[..., object]
    doc: str = ""

    @property
    def sql_name(self) -> str:
        return f"mathql_{self.name}"

    def signature(self) -> Signature:
        return Signature(self.arg_types, self.result_ty)
```

We could also add `doc: str = ""` so each function has documentation upon implementation.

One deliberate difference from `PostFunction`: `PostFunction.implementation` receives
one list of arguments (`implementation(args)`), while `CallbackFunction.implementation`
receives them spread out (`implementation(*args)`). Spread-out arguments let each
function name and type its parameters (`def _non_edges(n: int, m: int) -> int`), which
strict mypy can check. With one list, every function would first have to unpack and
check `object` values itself.



## Functions

For a start, we implement a test function in a separate file `functions.py` where we can later add more functions.
Right now the input and output of functions can only be `IntType | BoolType | StringType | ListType | ProductType` as defined in `mathql/types.py`.

Quick function: how many edges are missing for the graph to be complete.

```py
def _non_edges(n: int, m: int) -> int:  # n ... vertices, m ... edges
    return n * (n - 1) // 2 - m
```

The function does not check for `None`: when any argument is NULL (an absent value),
the wrapper in `execute.py` returns NULL without calling it, the way SQL's own
functions behave. So every function can assume its arguments are present.

```py
CallbackFunction("non_edges", (IntType(), IntType()), IntType(), _non_edges)
```
Example condition:
```json
"condition": "non_edges(g.num_vertices, g.num_edges) == 0"
```


## Additional ideas and questions
- Should `CallbackFunction` and `PostFunction` have a field `doc` where we could tell what each function does?
  `CallbackFunction` gets one now. `PostFunction` can get one later, in its own change.
- Should we add a Lean signature?
In [`bridge-query-language/MathQL/MathQL/Database.lean`](../../bridge-query-language/MathQL/MathQL/Database.lean) on line 45 there are the signatures of functions.

```lean
structure Database where
  ...
  /-- SQL functions -/
  sqlFunction : List (Ident × (List Ty × Ty) × String)
  /-- Postprocessing functions -/
  postFunction : List (Ident × (List Ty × Ty) × (List Lean.Json → Result Lean.Json))
  ...
```
I propose we use the same signature as `sqlFunction`. 
- Can we do a similar thing in PostgreSQL?
    Claude says:
        Partly. PostgreSQL can run Python functions (PL/Python), but they must be installed on
        the database server with `CREATE FUNCTION`; a program cannot register them on its
        connection the way SQLite allows. Out of scope for this plan.
    TODO: Verify this


# Concrete implementation

- add to `src/bridge_mcp/mathql/database.py`
    - ```py
        @dataclass(frozen=True)
        class CallbackFunction:
            """A Python function a query can call while SQLite reads the rows: its MathQL name,
            its signature, an implementation over the decoded argument values, and a human
            description. SQLite knows it as `mathql_` followed by its name."""

            name: str
            arg_types: tuple[Ty, ...]
            result_ty: Ty
            implementation: Callable[..., object]
            doc: str = ""

            @property
            def sql_name(self) -> str:
                return f"mathql_{self.name}"

            def signature(self) -> Signature:
                return Signature(self.arg_types, self.result_ty)
        ```
    - In class `Database` (line 107) add a field `callback_functions: tuple[CallbackFunction, ...] = ()`
    - On line 133 `functions={f.name: f.signature() for f in self.sql_functions},` turns into   
    ```py
        def __post_init__(self) -> None:
            names = [f.name for f in (*self.sql_functions, *self.callback_functions)]
            duplicates = sorted({name for name in names if names.count(name) > 1})
            if duplicates:
                raise ValueError(f"functions declared twice: {', '.join(duplicates)}")
    ```
    - On line 133 `functions={f.name: f.signature() for f in self.sql_functions},` turns into
    ```py
    functions={
        f.name: f.signature()
        for f in (*self.sql_functions, *self.callback_functions)
    },
    ```
    - Add `"functions"` to `describe` (line 144)
    ```py
            "constants": [{"name": c.name, "type": render_type(c.ty)} for c in self.constants],
            "functions": [
                {
                    "name": f.name,
                    "arguments": [render_type(t) for t in f.arg_types],
                    "result": render_type(f.result_ty),
                    "doc": f.doc,
                }
                for f in self.callback_functions
            ],
            "examples": [{"note": e.note, "query": e.query} for e in self.examples],
    ```

- change `compile.py` line 255
    ```py
    functions = {f.name: f.sql_name for f in database.sql_functions}
    ```
    turns into
    ```py
    functions = {
        f.name: f.sql_name for f in (*database.sql_functions, *database.callback_functions)
    }
    ```
- In `execute.py`

    Why encode and decode at all: SQLite stores only a few kinds of values (integers,
    text, NULL, ...). It has no booleans and no lists. So the database keeps a boolean as
    `0`/`1` and a list or a tuple as JSON text like `"[1,2]"`. When SQLite calls our
    function, it hands over these stored forms, so we first **decode** them into Python
    values (`1` → `True`, `"[1,2]"` → `[1, 2]`). The function's Python result must then be
    **encoded** back into a stored form (`True` → `1`, `[1, 2]` → `"[1,2]"`), because
    SQLite cannot hold a Python bool or list.

    - `_encode_cell(ty, value)` — Python result → what SQLite can store. A `bool` becomes
    `0`/`1`, a list becomes JSON text, `None` becomes `NULL`. (The reverse,
    `_decode_cell`, already exists in this file.)
    - `_as_callback(function)` — builds the small wrapper that SQLite actually calls for each
    row. It:
        1. returns `NULL` straight away when any argument is `NULL`, without calling the
           function;
        2. decodes each argument with `_decode_cell` (e.g. `0/1` → `False/True`);
        3. calls `function.implementation(*args)`;
        4. encodes the result with `_encode_cell`;
        5. if the function raises `MathQLError`, `ValueError` or `ArithmeticError`, returns
            `NULL` instead — one bad row then means "unknown" for that row, it does not crash
            the whole query.

       Encoding stays outside the `try` on purpose: a result of the wrong type is a bug in
       the function, not a property of one row, so it should stop the query rather than
       hide as NULL. Note that SQLite replaces any exception raised inside a callback with
       the vague `sqlite3.OperationalError: user-defined function raised exception`. While
       debugging, `sqlite3.enable_callback_tracebacks(True)` prints the real error.
    - `register_callbacks(connection, database)` — registers every callback function of
      the database on the connection.
    - add `CallbackFunction` to the import from `bridge_mcp.mathql.database`.
    ```py
    def _encode_cell(ty: Ty, value: object) -> int | str | None:
        """A value as SQLite stores it at `ty`, the inverse of `_decode_cell`: a boolean as 0
        or 1, a list or a product as JSON text, and None as NULL."""
        if value is None:
            return None
        else:
            match ty:
                case IntType():
                    return _as_int(value)
                case BoolType():
                    return int(_as_bool(value))
                case StringType():
                    return _as_str(value)
                case ListType() | ProductType():
                    return canonical(value)
            assert_never(ty)


    def _as_callback(function: CallbackFunction) -> Callable[..., int | str | None]:
        """`function` as SQLite calls it: on the stored argument values, returning the stored
        result. A NULL argument yields NULL without calling the implementation. A
        `MathQLError`, `ValueError` or `ArithmeticError` from the implementation yields
        NULL, so one row it rejects does not abort the query."""

        def call(*cells: object) -> int | str | None:
            if any(cell is None for cell in cells):
                return None
            args = [_decode_cell(ty, cell) for ty, cell in zip(function.arg_types, cells, strict=True)]
            try:
                result = function.implementation(*args)
            except (MathQLError, ValueError, ArithmeticError):
                return None
            return _encode_cell(function.result_ty, result)

        return call


    def register_callbacks(connection: sqlite3.Connection, database: Database) -> None:
        """Make each callback function of `database` callable on `connection` under its SQL name."""
        for function in database.callback_functions:
            connection.create_function(
                function.sql_name,
                len(function.arg_types),
                _as_callback(function),
                deterministic=True,
            )
    ```
- In `src/bridge_mcp/databases.py`
    - Add `register_callbacks(connection, database)` to `_open` (line)

- Add `src/bridge_mcp/mathql/databases/functions.py` and one example function
    ```py
    """Python functions a query can call while SQLite reads the rows."""

    from bridge_mcp.mathql.database import CallbackFunction
    from bridge_mcp.mathql.types import IntType


    def _non_edges(n: int, m: int) -> int:
        """How many edges a graph on `n` vertices with `m` edges lacks to be complete."""
        return n * (n - 1) // 2 - m


    NON_EDGES = CallbackFunction(
        "non_edges",
        (IntType(), IntType()),
        IntType(),
        _non_edges,
        doc="the number of edges a graph on n vertices with m edges lacks to be complete",
    )
    ```
- `src/bridge_mcp/mathql/databases/math_data.py`
    - add `functions` to the import: `from bridge_mcp.mathql.databases import functions, groups, pibase, provenance`
    - add to the examples, and pass the callback functions to `Database`:
    ```py
        Example(
                "the complete graphs: no edge is missing",
                {
                    "domains": [["g", "Graph"]],
                    "output": [["graph6", "g.graph6"], ["n", "g.num_vertices"]],
                    "condition": "non_edges(g.num_vertices, g.num_edges) == 0",
                },
            ),
        ),
        callback_functions=(functions.NON_EDGES,),
    )
    ```

- `src/bridge_mcp/mathql/tools.py` in `_database_section`  before the `### Examples` line, add:
    ```py
        if schema["functions"]:
            lines += ["", "### Functions, written `f(x, y)`"]
            for function in schema["functions"]:
                arguments = ", ".join(function["arguments"])
                lines.append(
                    f"- {function['name']}({arguments}) : {function['result']} — {function['doc']}"
                )
    ```


# TODO
- add tests: give the toy database in `tests/toy.py` a callback function, and test
    - a query whose condition calls it;
    - a NULL argument yields NULL without calling the function;
    - a function raising `MathQLError` yields NULL for that row only;
    - a function returning the wrong type stops the query;
    - two functions with the same name are rejected.
