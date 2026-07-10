#!/usr/bin/env python3
"""Fill the pibase_* tables of math-data.db from the π-Base bundle.

Fetches the compiled bundle (or reads a local copy with --file), computes the
deductive closure with provenance, and rebuilds the pibase_* tables inside the
existing database; the graph table is left untouched.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import urllib.request
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from bridge_mcp.pibase.deduction import database_closure, literals

BUNDLE_URL = "https://pub-65041ca69d744da88ade13abd31ad834.r2.dev/refs/heads/main.json"
DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "bridge_mcp"
    / "mathql"
    / "databases"
    / "math-data.db"
)

TABLES = """
DROP TABLE IF EXISTS pibase_space;
DROP TABLE IF EXISTS pibase_property;
DROP TABLE IF EXISTS pibase_theorem;
DROP TABLE IF EXISTS pibase_trait;
CREATE TABLE pibase_space (
    uid TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL,
    description TEXT NOT NULL,
    counterexamples_id INTEGER,
    refs TEXT NOT NULL);
CREATE TABLE pibase_property (
    uid TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL,
    description TEXT NOT NULL,
    refs TEXT NOT NULL);
CREATE TABLE pibase_theorem (
    uid TEXT NOT NULL PRIMARY KEY,
    statement TEXT NOT NULL,
    when_json TEXT NOT NULL,
    then_json TEXT NOT NULL,
    description TEXT NOT NULL,
    refs TEXT NOT NULL);
CREATE TABLE pibase_trait (
    space TEXT NOT NULL,
    property TEXT NOT NULL,
    value INTEGER NOT NULL,
    asserted INTEGER NOT NULL,
    theorem TEXT,
    premises TEXT NOT NULL,
    description TEXT NOT NULL,
    refs TEXT NOT NULL,
    PRIMARY KEY (space, property),
    FOREIGN KEY (space) REFERENCES pibase_space(uid),
    FOREIGN KEY (property) REFERENCES pibase_property(uid),
    FOREIGN KEY (theorem) REFERENCES pibase_theorem(uid));
"""


def fetch_bundle(file: str | None) -> dict[str, Any]:
    """The bundle from the local `file`, or downloaded from `BUNDLE_URL`."""
    if file is not None:
        loaded: dict[str, Any] = json.loads(Path(file).read_text(encoding="utf-8"))
    else:
        logging.info("fetching %s", BUNDLE_URL)
        with urllib.request.urlopen(BUNDLE_URL) as response:
            loaded = json.load(response)
    return loaded


def compact(value: object) -> str:
    """Minified JSON, comparing equal to SQLite's `json_array` output."""
    return json.dumps(value, separators=(",", ":"))


def rendered_ref(ref: Mapping[str, Any]) -> str:
    """One reference as `kind:identifier — name`."""
    kind, identifier = next((k, v) for k, v in ref.items() if k != "name")
    return f"{kind}:{identifier} — {ref.get('name', '')}"


def rendered_refs(refs: Iterable[Mapping[str, Any]]) -> str:
    return compact([rendered_ref(ref) for ref in refs])


def rendered_formula(formula: Mapping[str, Any], names: Mapping[str, str]) -> str:
    """A conjunctive formula with property names, e.g. `Compact ∧ ¬Metrizable`."""
    return " ∧ ".join(
        names[literal.property] if literal.value else f"¬{names[literal.property]}"
        for literal in literals(formula)
    )


def space_rows(spaces: Iterable[Mapping[str, Any]]) -> list[tuple[object, ...]]:
    return [
        (
            space["uid"],
            space["name"],
            compact(space.get("aliases", [])),
            space["description"].strip(),
            space.get("counterexamples_id"),
            rendered_refs(space.get("refs", [])),
        )
        for space in spaces
    ]


def property_rows(properties: Iterable[Mapping[str, Any]]) -> list[tuple[object, ...]]:
    return [
        (
            prop["uid"],
            prop["name"],
            compact(prop.get("aliases", [])),
            prop["description"].strip(),
            rendered_refs(prop.get("refs", [])),
        )
        for prop in properties
    ]


def theorem_rows(
    theorems: Iterable[Mapping[str, Any]], names: Mapping[str, str]
) -> list[tuple[object, ...]]:
    return [
        (
            theorem["uid"],
            f"{rendered_formula(theorem['when'], names)}"
            f" ⇒ {rendered_formula(theorem['then'], names)}",
            compact(theorem["when"]),
            compact(theorem["then"]),
            theorem["description"].strip(),
            rendered_refs(theorem.get("refs", [])),
        )
        for theorem in theorems
    ]


def trait_rows(bundle: Mapping[str, Any]) -> tuple[list[tuple[object, ...]], int]:
    """All trait rows — asserted from the bundle, then the deduced closure — and
    the number of derived ones."""
    asserted: list[tuple[object, ...]] = [
        (
            trait["space"],
            trait["property"],
            int(trait["value"]),
            1,
            None,
            "[]",
            trait["description"].strip(),
            rendered_refs(trait.get("refs", [])),
        )
        for trait in bundle["traits"]
    ]
    derived: list[tuple[object, ...]] = [
        (
            space,
            prop,
            int(fact.literal.value),
            0,
            fact.theorem,
            compact([[premise.property, premise.value] for premise in fact.premises]),
            "",
            "[]",
        )
        for space, facts in database_closure(bundle["traits"], bundle["theorems"]).items()
        for prop, fact in facts.items()
    ]
    return asserted + derived, len(derived)


def main(file: str | None) -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found; run scripts/generate_graphs.py first")
    bundle = fetch_bundle(file)
    names = {prop["uid"]: str(prop["name"]) for prop in bundle["properties"]}
    traits, derived = trait_rows(bundle)
    connection = sqlite3.connect(DB_PATH)
    connection.executescript(TABLES)
    connection.executemany(
        "INSERT INTO pibase_space VALUES (?, ?, ?, ?, ?, ?)", space_rows(bundle["spaces"])
    )
    connection.executemany(
        "INSERT INTO pibase_property VALUES (?, ?, ?, ?, ?)",
        property_rows(bundle["properties"]),
    )
    connection.executemany(
        "INSERT INTO pibase_theorem VALUES (?, ?, ?, ?, ?, ?)",
        theorem_rows(bundle["theorems"], names),
    )
    connection.executemany("INSERT INTO pibase_trait VALUES (?, ?, ?, ?, ?, ?, ?, ?)", traits)
    connection.commit()
    connection.close()
    logging.info(
        "wrote %s from bundle %s: %d spaces, %d properties, %d theorems, "
        "%d asserted + %d derived traits",
        DB_PATH,
        bundle.get("version", {}).get("sha", "unknown"),
        len(bundle["spaces"]),
        len(bundle["properties"]),
        len(bundle["theorems"]),
        len(bundle["traits"]),
        derived,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="read the bundle from a local file instead")
    main(parser.parse_args().file)
