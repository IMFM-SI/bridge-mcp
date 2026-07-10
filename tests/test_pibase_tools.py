"""Checks for the π-Base search and derivation tools, against the bundled database."""

import contextlib
import sqlite3
from typing import Any

import pytest

from bridge_mcp.mathql.execute import database_path
from bridge_mcp.pibase.tools import derivation, search


@pytest.fixture(autouse=True)
def _require_pibase_tables() -> None:
    path = database_path()
    if not path.exists():
        pytest.skip(f"{path} not present; run python -m bridge_mcp.generate graphs")
    with contextlib.closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as conn:
        generated = conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'pibase_space'"
        ).fetchone()
    if generated is None:
        pytest.skip("pibase tables not present; run python -m bridge_mcp.generate pibase")


def test_search_exact_name() -> None:
    top = search("cantor")[0]
    assert top["kind"] == "space"
    assert top["name"] == "Cantor space $2^\\omega$"


def test_search_alias_and_misspelling() -> None:
    top = search("hausdorf", kind="property")[0]
    assert top["name"] == "$T_2$"  # matched through the Hausdorff alias
    assert search("metrizible", kind="property")[0]["name"] == "Metrizable"


def test_search_symbolic_name() -> None:
    assert search("T2", kind="property")[0]["name"] == "$T_2$"


def test_search_theorem_statements() -> None:
    results = search("compact", kind="theorem", limit=5)
    assert len(results) == 5
    assert all(result["kind"] == "theorem" for result in results)


def test_search_respects_limit_and_kind() -> None:
    results = search("line", limit=3)
    assert len(results) == 3
    with pytest.raises(ValueError):
        search("line", kind="bogus")


def test_derivation_tree() -> None:
    tree: Any = derivation("S000149", "P000053")
    assert tree["space"] == "Two-sided long line"
    trait = tree["trait"]
    assert trait["value"] is False

    def leaves(node: Any) -> list[Any]:
        if "premises" in node:
            assert node["statement"]
            return [leaf for premise in node["premises"] for leaf in leaves(premise)]
        else:
            assert node["asserted"] is True
            return [node]

    assert leaves(trait)  # every branch terminates in an asserted fact


def test_derivation_unknown() -> None:
    with pytest.raises(ValueError):
        derivation("S999999", "P000053")
    with pytest.raises(ValueError):
        derivation("S000149", "P999999")
