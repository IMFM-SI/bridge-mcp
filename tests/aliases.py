"""The safe-alias predicate for tests that compile without a connection."""

from __future__ import annotations

from collections.abc import Callable

from bridge_mcp.mathql.database import Database


def safe_alias(database: Database) -> Callable[[str], bool]:
    """A name is a safe alias when no column the database declares bears it. Production
    reads the same names from the open connection with `execute.safe_alias_predicate`."""
    declared = {
        column.column.lower()
        for schema in database.domains.values()
        for column in schema.columns.values()
    }
    keys = {
        name.lower()
        for schema in database.domains.values()
        for foreign in schema.foreign_keys.values()
        for pair in foreign.columns
        for name in pair
    }
    taken = declared | keys | {"rowid", "oid", "_rowid_"}
    return lambda name: name.lower() not in taken
