"""The typing context: the domains available, the variables bound, and the constants."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from bridge_mcp.mathql.types import Ty


@dataclass(frozen=True)
class DomainSignature:
    """A domain's typing view: its queryable fields and its output-field labels."""

    input_fields: Mapping[str, Ty]
    output_fields: frozenset[str]


@dataclass(frozen=True)
class Context:
    """Which domains are available, which variables are bound, and the constants."""

    domains: Mapping[str, DomainSignature]
    variables: Mapping[str, DomainSignature] = field(default_factory=dict)
    constants: Mapping[str, Ty] = field(default_factory=dict)

    def with_variables(self, additions: Mapping[str, DomainSignature]) -> Context:
        return replace(self, variables={**self.variables, **additions})

    def lookup_variable(self, var: str) -> DomainSignature | None:
        return self.variables.get(var)

    def lookup_constant(self, name: str) -> Ty | None:
        return self.constants.get(name)

    def lookup_input_field(self, var: str, label: str) -> Ty | None:
        signature = self.variables.get(var)
        return signature.input_fields.get(label) if signature is not None else None

    def is_output_field(self, var: str, label: str) -> bool:
        signature = self.variables.get(var)
        return signature is not None and label in signature.output_fields
