"""Reporting a tool's anticipated failures."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError


def anticipating(
    *kinds: type[Exception],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap a tool so that a failure of one of `kinds` raises `ToolError` carrying its
    message, which the SDK returns as the tool's result with `is_error` set, for the model
    to read and act on. Every other exception stays a crash, whose traceback the SDK logs
    and whose message it withholds."""

    def wrap(tool: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(tool)
        def anticipated(*arguments: Any, **keywords: Any) -> Any:
            try:
                return tool(*arguments, **keywords)
            except kinds as failure:
                raise ToolError(str(failure)) from failure

        return anticipated

    return wrap
