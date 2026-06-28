# Contributing

If you would like to contribute to the project, you should set up the development version of the Python environemnt
and download dependencies.

## Developer setup

Clone the [`bridge-mcp` repository](https://github.com/IMFM-SI/bridge-mcp), possibly after forking it:

    git clone git@github.com:IMFM-SI/bridge-mcp.git

Set up the local Python environment with the needed development tools:

    cd bridge-mcp
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"

## Dependencies

`pip install -e ".[dev]"` installs the project in editable mode together with its runtime
and development dependencies, declared in `pyproject.toml`:

- runtime: `mcp[cli]` (the Model Context Protocol SDK and its `mcp` command-line tool),
  `lark` (the query-language parser), and `networkx` (the graph tools and the database
  generator);
- development: `pytest` (tests), `mypy` (type checking), and `ruff` (linting and
  formatting).

These pull in a number of transitive dependencies. For the exact resolved set installed
in your environment, run `pip list`.

## Usage

You should always work with the local Python environment, which you activate by running
`source .venv/bin/activate` in the `bridge-mcp` directory.

You can now run the server locally with

    mcp dev src/bridge_mcp/server.py

You can also run the following commands:

* `pytest` – run tests
* `mypy src` – typecheck the source code
* `ruff check .` – check the code with linter
* `ruff format --check .` – check the source code formatting

If you install [nauty](https://pallini.di.uniroma1.it) you can regenerate the graphs database with

    python scripts/generate_graphs.py

The script assumes nauty's `geng` is on the `PATH`.
