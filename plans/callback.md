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
I would add `sql_name` so the names of the native SQLite functions don't get mixed up with Python functions. Each python function could have `mathql_` prefix. We could implement 
```py
@dataclass(frozen=True)
class CallbackFunction:
    name: str                      # name used in query
    arg_types: tuple[Ty, ...]
    result_ty: Ty 
    sql_name: str                  # name registered in SQLite
    implementation: Callable[..., object]   # the Python function

    def signature(self) -> Signature:
        return Signature(self.arg_types, self.result_ty)
```

We could also add `doc: str = ""` so each fuction has a documentation upon implementation.


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


## Functions

For a start, we could implement a test function in a separate file `functions.py` where we could later add more functions.
Right now the input and output of functions can only be `IntType | BoolType | StringType | ListType | ProductType` as defined in `mathql/types.py`.

Quick function: how many edges are missing for the graph to be complete.

```py
def _non_edges(n, m): # n ... vertices, m ... edges
    if n is None or m is None:
        return None
    return n * (n - 1) // 2 - m
```

```py 
CallbackFunction("non_edges", (IntType(), IntType()), IntType(), "mathql_non_edges", _non_edges)
```
Example condition:
```json
"condition": "non_edges(g.num_vertices, g.num_edges) == 0"
```


## Additional ideas and questions
- Should `CallbackFunction` and `PostFunction` have a field `doc` where we could tell what each function does?
- Should we add a Lean signature?
```lean
  /-- Callback functions -/
  callbackFunction : List (Ident × (List Ty × Ty) × String)
```
- Can we do a similar thing in PostgreSQL?


# Concrete implementation

- add to `database.py`
    ```py
    class CallbackFunction:
    """A Python function callable in the condition, the output, and the order: its MathQL
    name, its signature, the name it is registered under in SQLite, an implementation
    over the decoded argument values, and a human description."""
    name: str
    arg_types: tuple[Ty, ...]
    result_ty: Ty
    sql_name: str1
    implementation: Callable[..., object]
    doc: str = ""
        
    def signature(self) -> Signature:
        return Signature(self.arg_types, self.result_ty)
    ```

- change `compile.py` line 255
    ```py 
    functions = {f.name: f.sql_name for f in database.sql_functions}
    ```
    turns into
    ```py 
    functions = {f.name: f.sql_name for f in (*database.sql_functions, *database.callback_functions)}
    ```
- New `src/bridge_mcp/mathql/databases/functions.py`:
    ```py 
    def _non_edges(n: int, m: int) -> int:
    """How many edges are missing for the graph to be complete."""
    return n * (n - 1) // 2 - m

    NON_EDGES = CallbackFunction(
        "non_edges", (IntType(), IntType()), IntType(), "mathql_non_edges", _non_edges,
        doc="non_edges(n, m): the number of edges missing from a graph on n vertices with m edges",
    )
    ```
