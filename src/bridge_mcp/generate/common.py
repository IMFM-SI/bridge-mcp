"""Shared pieces of the database generators."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from importlib.metadata import version
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "mathql" / "databases" / "math-data.db"

SourceRow = tuple[str, str, str | None, str, str | None, str | None]
"""A source: id, tool, version, description, retrieved, attribution."""

ProvenanceRow = tuple[str, str, str, str]
"""A provenance entry: domain, field, source id, note."""

PROVENANCE_TABLES = """
CREATE TABLE IF NOT EXISTS source (
    id TEXT NOT NULL PRIMARY KEY,
    tool TEXT NOT NULL,
    version TEXT,
    description TEXT NOT NULL,
    retrieved TEXT,
    attribution TEXT);
CREATE TABLE IF NOT EXISTS provenance (
    domain TEXT NOT NULL,
    field TEXT NOT NULL,
    source TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (domain, field, source),
    FOREIGN KEY (source) REFERENCES source(id));
"""


def compact(value: object) -> str:
    """Minified JSON, comparing equal to SQLite's `json_array` output."""
    return json.dumps(value, separators=(",", ":"))


def bridge_mcp_source() -> SourceRow:
    """The source row for facts bridge-mcp computes itself."""
    return (
        "bridge-mcp",
        "bridge-mcp",
        version("bridge-mcp"),
        "facts computed by bridge-mcp itself: derived traits, rendered statements, "
        "Cayley graphs, automorphism identification, and bookkeeping fields",
        None,
        None,
    )


def record_sources(connection: sqlite3.Connection, rows: Iterable[SourceRow]) -> None:
    """Insert or update the given source rows."""
    connection.executescript(PROVENANCE_TABLES)
    connection.executemany("INSERT OR REPLACE INTO source VALUES (?, ?, ?, ?, ?, ?)", rows)


def record_provenance(
    connection: sqlite3.Connection,
    domains: Iterable[str],
    rows: Iterable[ProvenanceRow],
) -> None:
    """Replace the provenance rows of the given domains."""
    connection.executescript(PROVENANCE_TABLES)
    connection.executemany(
        "DELETE FROM provenance WHERE domain = ?", [(domain,) for domain in domains]
    )
    connection.executemany("INSERT INTO provenance VALUES (?, ?, ?, ?)", rows)
