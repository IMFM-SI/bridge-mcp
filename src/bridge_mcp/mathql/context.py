"""The typing context: the domains available and the identifiers in scope."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.types import Ty


@dataclass(frozen=True)
class InputField:
    """A scalar field: its type and whether it is part of the primary key."""

    ty: Ty
    is_primary: bool


@dataclass(frozen=True)
class DomainTy:
    """The typing view of a domain: its scalar fields and its links to other domains."""

    input_fields: Mapping[str, InputField]
    domain_fields: Mapping[str, str]


@dataclass(frozen=True)
class TypeEntry:
    """An identifier denoting a value: a constant or an output alias."""

    ty: Ty


@dataclass(frozen=True)
class DomainEntry:
    """An identifier denoting an object: a domain variable."""

    domain: str


Entry = TypeEntry | DomainEntry


@dataclass(frozen=True)
class Context:
    """The domains available and the entry of each identifier in scope."""

    domains: Mapping[str, DomainTy]
    idents: Mapping[str, Entry] = field(default_factory=dict)

    def get_ident(self, name: str) -> Ty:
        match self.idents.get(name):
            case TypeEntry(ty):
                return ty
            case DomainEntry():
                raise MathQLError(f"{name} is a domain but a constant was expected")
            case None:
                raise MathQLError(f"unknown identifier {name}")

    def get_domain_ident(self, name: str) -> str:
        match self.idents.get(name):
            case DomainEntry(domain):
                return domain
            case TypeEntry():
                raise MathQLError(f"{name} is a constant but a domain was expected")
            case None:
                raise MathQLError(f"unknown domain name {name}")

    def get_domain(self, domain: str) -> DomainTy:
        match self.domains.get(domain):
            case None:
                raise MathQLError(f"unknown domain {domain}")
            case domain_ty:
                return domain_ty

    def get_primary_key(self, domain: str) -> tuple[tuple[str, Ty], ...]:
        """The labels and types of the domain's primary-key fields, in field order."""
        return tuple(
            (label, input_field.ty)
            for label, input_field in self.get_domain(domain).input_fields.items()
            if input_field.is_primary
        )

    def get_id_types(self, domain: str) -> tuple[Ty, ...]:
        return tuple(ty for _, ty in self.get_primary_key(domain))

    def get_input_field(self, domain: str, label: str) -> InputField:
        match self.get_domain(domain).input_fields.get(label):
            case None:
                raise MathQLError(f"domain {domain} does not have a field {label}")
            case input_field:
                return input_field

    def get_domain_field(self, domain: str, label: str) -> str:
        match self.get_domain(domain).domain_fields.get(label):
            case None:
                raise MathQLError(f"domain {domain} does not have a field {label}")
            case linked:
                return linked

    def get_input_field_ty(self, domain: str, label: str) -> Ty:
        return self.get_input_field(domain, label).ty

    def extend_ident(self, name: str, ty: Ty) -> Context:
        return replace(self, idents={**self.idents, name: TypeEntry(ty)})

    def extend_domain_ident(self, name: str, domain: str) -> Context:
        return replace(self, idents={**self.idents, name: DomainEntry(domain)})
