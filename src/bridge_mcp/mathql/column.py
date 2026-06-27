"""Codecs decoding a raw SQLite cell into a JSON-serializable value.

Each maps one column's cell to the value of the field it backs.
"""

import json
from typing import Any


def integer(cell: Any) -> int:
    return int(cell)


def boolean(cell: Any) -> bool:
    return bool(cell)


def text(cell: Any) -> str:
    return str(cell)


def optional_integer(cell: Any) -> int | None:
    return None if cell is None else int(cell)


def integer_list(cell: Any) -> list[int]:
    decoded: list[int] = json.loads(cell)
    return decoded
