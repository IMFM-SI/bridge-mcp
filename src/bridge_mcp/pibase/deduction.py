"""Deduction of derived π-Base traits, with provenance.

Facts are signed literals (a property holds or fails for a space), and each
theorem `l1 ∧ … ∧ ln → c` acts as the clause `¬l1 ∨ … ∨ ¬ln ∨ c`: unit
propagation applies it by modus ponens and by contrapositive, per space, to a
fixpoint. Every derived fact records the theorem of its final step and the
premise literals that step consumed, so the full derivation tree is
reconstructible by recursion.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Literal:
    """A signed atom: the property holds (`value` True) or fails."""

    property: str
    value: bool


@dataclass(frozen=True)
class Rule:
    """A theorem normalized to a single consequent literal."""

    theorem: str
    antecedents: tuple[Literal, ...]
    consequent: Literal


@dataclass(frozen=True)
class Derived:
    """A derived fact: its literal, the theorem of the final derivation step,
    and the premise literals that step consumed."""

    literal: Literal
    theorem: str
    premises: tuple[Literal, ...]


def literals(formula: Mapping[str, Any]) -> tuple[Literal, ...]:
    """The literals of a conjunctive formula; any other shape is an error."""
    match formula.get("kind"):
        case "atom":
            return (Literal(str(formula["property"]), bool(formula["value"])),)
        case "and":
            return tuple(literal for sub in formula["subs"] for literal in literals(sub))
        case kind:
            raise ValueError(f"unsupported formula kind {kind!r}")


def rules(theorems: Iterable[Mapping[str, Any]]) -> tuple[Rule, ...]:
    """Normalize theorems to single-consequent rules; a conjunctive consequent
    yields one rule per conclusion literal."""
    return tuple(
        Rule(str(theorem["uid"]), literals(theorem["when"]), conclusion)
        for theorem in theorems
        for conclusion in literals(theorem["then"])
    )


def closure(asserted: Mapping[str, bool], normalized: Sequence[Rule]) -> dict[str, Derived]:
    """The deductive closure of one space's asserted traits, keyed by property.

    Raises `ValueError` when a rule concludes the opposite of a known fact.
    """
    known: dict[str, bool] = dict(asserted)
    derived: dict[str, Derived] = {}

    def holds(literal: Literal) -> bool | None:
        value = known.get(literal.property)
        return None if value is None else value == literal.value

    def conclude(conclusion: Literal, theorem: str, premises: tuple[Literal, ...]) -> bool:
        """Record a concluded literal; False when it was already known."""
        match holds(conclusion):
            case True:
                return False
            case False:
                raise ValueError(
                    f"{theorem} concludes {conclusion.property} = "
                    f"{str(conclusion.value).lower()}, contradicting the known value"
                )
            case _:
                known[conclusion.property] = conclusion.value
                derived[conclusion.property] = Derived(conclusion, theorem, premises)
                return True

    def fire(rule: Rule) -> bool:
        """Apply one rule by modus ponens or by contrapositive."""
        statuses = [(literal, holds(literal)) for literal in rule.antecedents]
        unknown = [literal for literal, status in statuses if status is None]
        violated = any(status is False for _, status in statuses)
        if not unknown and not violated:
            return conclude(rule.consequent, rule.theorem, rule.antecedents)
        elif holds(rule.consequent) is False and len(unknown) == 1 and not violated:
            refuted = Literal(rule.consequent.property, not rule.consequent.value)
            satisfied = tuple(literal for literal, status in statuses if status is True)
            return conclude(
                Literal(unknown[0].property, not unknown[0].value),
                rule.theorem,
                (refuted, *satisfied),
            )
        else:
            return False

    progress = True
    while progress:
        progress = False
        for rule in normalized:
            progress = fire(rule) or progress
    return derived


def database_closure(
    traits: Iterable[Mapping[str, Any]], theorems: Iterable[Mapping[str, Any]]
) -> dict[str, dict[str, Derived]]:
    """The closure of every space's asserted traits: space → property → Derived.

    `traits` and `theorems` are the bundle's lists; a contradiction is reported
    with its space uid.
    """
    normalized = rules(theorems)
    asserted: dict[str, dict[str, bool]] = {}
    for trait in traits:
        by_space = asserted.setdefault(str(trait["space"]), {})
        by_space[str(trait["property"])] = bool(trait["value"])

    def space_closure(space: str, facts: Mapping[str, bool]) -> dict[str, Derived]:
        try:
            return closure(facts, normalized)
        except ValueError as error:
            raise ValueError(f"{space}: {error}") from None

    return {space: space_closure(space, facts) for space, facts in asserted.items()}
