"""Errors raised while parsing, type-checking, or compiling a MathQL query."""


class MathQLError(Exception):
    """A MathQL query is malformed or ill-typed."""
