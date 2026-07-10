"""Shared pieces of the database generators."""

from __future__ import annotations

import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "mathql" / "databases" / "math-data.db"


def compact(value: object) -> str:
    """Minified JSON, comparing equal to SQLite's `json_array` output."""
    return json.dumps(value, separators=(",", ":"))
