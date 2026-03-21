"""Tool provider protocol and shared types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolResult:
    """Return value from a tool invocation."""
    content: str
    token_estimate: int = 0


def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple heuristic (~4 chars per token)."""
    return max(1, len(text) // 4)


class ToolProvider(Protocol):
    """Interface that all condition-specific tool sets implement."""

    @property
    def condition_name(self) -> str: ...

    @property
    def tool_definitions(self) -> list[dict[str, Any]]: ...

    def call(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult: ...
