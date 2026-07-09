"""The database: how domains, their fields, and the constants map to SQLite."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from bridge_mcp.mathql import sql
from bridge_mcp.mathql.context import Context, DomainTy, Entry, InputField, TypeEntry
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.types import Ty
from bridge_mcp.mathql.types import render as render_type


@dataclass(frozen=True)
class Column:
    """A scalar field: the backing column, its type, whether it is part of the primary
    key, and a human description."""

    column: str
    ty: Ty
    is_primary: bool
    doc: str


@dataclass(frozen=True)
class ForeignKey:
    """A domain-valued field: the domain it links to, the matching column pairs
    (this table's column, the foreign table's column), and a human description."""

    domain: str
    columns: tuple[tuple[str, str], ...]
    doc: str


@dataclass(frozen=True)
class Schema:
    """A domain's realization: the table, the scalar fields and foreign keys each keyed
    by label, and a human description."""

    table: str
    columns: Mapping[str, Column]
    foreign_keys: Mapping[str, ForeignKey]
    doc: str

    def primary_columns(self) -> tuple[str, ...]:
        return tuple(c.column for c in self.columns.values() if c.is_primary)

    def get_foreign_key(self, label: str) -> ForeignKey:
        match self.foreign_keys.get(label):
            case None:
                raise MathQLError(f"unknown foreign key {label}")
            case foreign_key:
                return foreign_key


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
    domains: Mapping[str, Schema]
    examples: tuple[Example, ...]

    def domain_context(self) -> dict[str, DomainTy]:
        return {
            name: DomainTy(
                input_fields={
                    label: InputField(c.ty, c.is_primary)
                    for label, c in schema.columns.items()
                },
                domain_fields={label: fk.domain for label, fk in schema.foreign_keys.items()},
            )
            for name, schema in self.domains.items()
        }

    def context(self) -> Context:
        idents: dict[str, Entry] = {c.name: TypeEntry(c.ty) for c in self.constants}
        return Context(domains=self.domain_context(), idents=idents)

    def describe(self) -> dict[str, object]:
        """The schema as JSON: the overview, each domain with its input and domain
        fields, the constants, and the example queries."""
        return {
            "overview": self.overview,
            "domains": [
                {
                    "name": name,
                    "doc": schema.doc,
                    "inputFields": [
                        {"label": label, "type": render_type(c.ty), "doc": c.doc}
                        for label, c in schema.columns.items()
                    ],
                    "domainFields": [
                        {"label": label, "domain": fk.domain, "doc": fk.doc}
                        for label, fk in schema.foreign_keys.items()
                    ],
                }
                for name, schema in self.domains.items()
            ],
            "constants": [{"name": c.name, "type": render_type(c.ty)} for c in self.constants],
            "examples": [{"note": e.note, "query": e.query} for e in self.examples],
        }
