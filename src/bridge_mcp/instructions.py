"""Compose the server instructions from the components' fragments."""

from collections.abc import Iterable


def build_instructions(fragments: Iterable[str]) -> str:
    return "\n\n".join(fragment.strip() for fragment in fragments if fragment.strip())
