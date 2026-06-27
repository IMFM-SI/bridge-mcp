"""The database abstraction: domains, their fields and codecs, and the schema."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.context import Context, DomainSignature
from bridge_mcp.mathql.types import Ty
from bridge_mcp.mathql.types import render as render_type


@dataclass(frozen=True)
class Field:
    """A field: its query-language label, the SQL column, its type, a codec, and a doc.

    Every field is both queryable (in a condition) and returnable (in the output).
    """

    label: str
    column: str
    ty: Ty
    doc: str
    codec: Callable[[Any], object]


@dataclass(frozen=True)
class Domain:
    table: str
    fields: tuple[Field, ...]
    doc: str

    def decode(self, cells: Sequence[Any]) -> dict[str, object]:
        """Decode this domain's slice of a result row into {label: value}."""
        return {
            field.label: field.codec(cell)
            for field, cell in zip(self.fields, cells, strict=True)
        }


@dataclass(frozen=True)
class Constant:
    name: str
    ty: Ty
    sql: sql.Expr


@dataclass(frozen=True)
class Example:
    note: str
    query: Mapping[str, object]


@dataclass(frozen=True)
class Database:
    overview: str
    constants: tuple[Constant, ...]
    domains: Mapping[str, Domain]
    examples: tuple[Example, ...]

    def typing_context(self) -> Context:
        signatures = {
            name: DomainSignature(
                input_fields={field.label: field.ty for field in domain.fields},
                output_fields=frozenset(field.label for field in domain.fields),
            )
            for name, domain in self.domains.items()
        }
        return Context(domains=signatures, constants={c.name: c.ty for c in self.constants})

    def sql_constants(self) -> dict[str, sql.Expr]:
        return {c.name: c.sql for c in self.constants}

    def describe(self) -> dict[str, object]:
        """The schema as JSON: overview, domains with fields, constants, and examples."""
        return {
            "overview": self.overview,
            "domains": [
                {
                    "name": name,
                    "doc": domain.doc,
                    "fields": [
                        {"label": field.label, "type": render_type(field.ty), "doc": field.doc}
                        for field in domain.fields
                    ],
                    "output": [field.label for field in domain.fields],
                }
                for name, domain in self.domains.items()
            ],
            "constants": [{"name": c.name, "type": render_type(c.ty)} for c in self.constants],
            "examples": [{"note": e.note, "query": e.query} for e in self.examples],
        }
