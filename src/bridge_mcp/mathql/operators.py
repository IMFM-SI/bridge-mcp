"""Operators of the query language, shared by the input and typed syntax."""

from enum import Enum, auto


class UnaryOp(Enum):
    NOT = auto()
    NEG = auto()


class BinaryOp(Enum):
    AND = auto()
    OR = auto()
    ADD = auto()
    SUB = auto()
    MUL = auto()


class ComparisonOp(Enum):
    EQ = auto()
    NE = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()


class Direction(Enum):
    ASC = auto()
    DESC = auto()
