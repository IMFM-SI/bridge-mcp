"""Checks for the column codecs."""

from bridge_mcp.mathql import column


def test_codecs() -> None:
    assert column.integer(5) == 5
    assert column.boolean(1) is True
    assert column.boolean(0) is False
    assert column.text("abc") == "abc"
    assert column.optional_integer(None) is None
    assert column.optional_integer(3) == 3
    assert column.integer_list("[2,2,2]") == [2, 2, 2]
