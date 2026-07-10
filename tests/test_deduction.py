"""Checks for the π-Base deduction engine, over toy theorem sets."""

from typing import Any

import pytest

from bridge_mcp.pibase.deduction import (
    Derived,
    Literal,
    closure,
    database_closure,
    literals,
    rules,
)


def atom(prop: str, value: bool = True) -> dict[str, Any]:
    return {"kind": "atom", "property": prop, "value": value}


def conj(*subs: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "and", "subs": list(subs)}


def theorem(uid: str, when: dict[str, Any], then: dict[str, Any]) -> dict[str, Any]:
    return {"uid": uid, "when": when, "then": then}


def test_literals() -> None:
    assert literals(atom("P1")) == (Literal("P1", True),)
    assert literals(conj(atom("P1"), atom("P2", False))) == (
        Literal("P1", True),
        Literal("P2", False),
    )
    with pytest.raises(ValueError):
        literals({"kind": "or", "subs": []})


def test_conjunctive_consequent_splits() -> None:
    normalized = rules([theorem("T1", atom("P1"), conj(atom("P2"), atom("P3", False)))])
    assert [rule.consequent for rule in normalized] == [
        Literal("P2", True),
        Literal("P3", False),
    ]
    assert all(rule.theorem == "T1" for rule in normalized)


def test_modus_ponens() -> None:
    normalized = rules([theorem("T1", atom("P1"), atom("P2"))])
    assert closure({"P1": True}, normalized) == {
        "P2": Derived(Literal("P2", True), "T1", (Literal("P1", True),))
    }


def test_negative_literals() -> None:
    normalized = rules([theorem("T1", conj(atom("P1"), atom("P2", False)), atom("P3", False))])
    derived = closure({"P1": True, "P2": False}, normalized)
    assert derived["P3"] == Derived(
        Literal("P3", False), "T1", (Literal("P1", True), Literal("P2", False))
    )


def test_contrapositive() -> None:
    normalized = rules([theorem("T1", atom("P1"), atom("P2"))])
    assert closure({"P2": False}, normalized) == {
        "P1": Derived(Literal("P1", False), "T1", (Literal("P2", False),))
    }


def test_contrapositive_of_conjunction() -> None:
    normalized = rules([theorem("T1", conj(atom("P1"), atom("P2")), atom("P3"))])
    derived = closure({"P3": False, "P1": True}, normalized)
    assert derived["P2"] == Derived(
        Literal("P2", False), "T1", (Literal("P3", False), Literal("P1", True))
    )


def test_chain_reconstructs_a_tree() -> None:
    normalized = rules(
        [theorem("T1", atom("P1"), atom("P2")), theorem("T2", atom("P2"), atom("P3"))]
    )
    derived = closure({"P1": True}, normalized)
    assert derived["P3"].theorem == "T2"
    assert derived["P3"].premises == (Literal("P2", True),)
    assert derived["P2"].theorem == "T1"  # the premise's own derivation


def test_chained_contrapositives() -> None:
    normalized = rules(
        [theorem("T1", atom("P1"), atom("P2")), theorem("T2", atom("P2"), atom("P3"))]
    )
    derived = closure({"P3": False}, normalized)
    assert derived["P2"].literal == Literal("P2", False)
    assert derived["P1"].literal == Literal("P1", False)


def test_nothing_to_derive() -> None:
    normalized = rules([theorem("T1", atom("P1"), atom("P2"))])
    assert closure({"P9": True}, normalized) == {}


def test_contradiction() -> None:
    normalized = rules([theorem("T1", atom("P1"), atom("P2"))])
    with pytest.raises(ValueError, match="T1"):
        closure({"P1": True, "P2": False}, normalized)


def test_database_closure_is_per_space() -> None:
    theorems = [theorem("T1", atom("P1"), atom("P2"))]
    traits = [
        {"space": "S1", "property": "P1", "value": True},
        {"space": "S2", "property": "P2", "value": False},
    ]
    result = database_closure(traits, theorems)
    assert result["S1"]["P2"].literal == Literal("P2", True)
    assert result["S2"]["P1"].literal == Literal("P1", False)


def test_database_closure_names_the_space_in_errors() -> None:
    theorems = [theorem("T1", atom("P1"), atom("P2"))]
    traits = [
        {"space": "S1", "property": "P1", "value": True},
        {"space": "S1", "property": "P2", "value": False},
    ]
    with pytest.raises(ValueError, match="S1"):
        database_closure(traits, theorems)
