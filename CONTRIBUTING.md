# Contributing

## Development setup

```
git clone <repo> && cd bridge-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"             # the package, editable, with the dev tools
pytest                              # run the tests
mypy src                            # strict type check
ruff check . && ruff format --check .
mcp dev src/bridge_mcp/server.py    # run the server in the MCP inspector
```

Regenerating the graphs database additionally needs nauty's `geng` on the PATH, for
`scripts/generate_graphs.py`.
