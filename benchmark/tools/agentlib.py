"""Condition C: AgentLib — 4 navigation tools calling storage layer directly."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from benchmark.tools.base import ToolResult, estimate_tokens


BROWSE_LIBRARY_SCHEMA: dict[str, Any] = {
    "name": "browse_library",
    "description": "List all books in the library with titles, tags, summaries, and chapter/chunk counts.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

OPEN_BOOK_SCHEMA: dict[str, Any] = {
    "name": "open_book",
    "description": "Get detailed chapter and section structure for a specific book, including summaries and concept index.",
    "input_schema": {
        "type": "object",
        "properties": {
            "book_id": {
                "type": "string",
                "description": "The book identifier (from browse_library).",
            },
        },
        "required": ["book_id"],
    },
}

READ_CHUNKS_SCHEMA: dict[str, Any] = {
    "name": "read_chunks",
    "description": "Read the full content of specific chunks by ID. Max 10 chunks per call.",
    "input_schema": {
        "type": "object",
        "properties": {
            "book_id": {
                "type": "string",
                "description": "The book identifier.",
            },
            "chunk_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of chunk IDs to read (max 10).",
                "maxItems": 10,
            },
        },
        "required": ["book_id", "chunk_ids"],
    },
}

SEARCH_CONCEPTS_SCHEMA: dict[str, Any] = {
    "name": "search_concepts",
    "description": "Search for concepts across all books (or a specific book). Returns matching concept names with their chapter, section, and chunk locations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string.",
            },
            "book_id": {
                "type": "string",
                "description": "Optional: limit search to a specific book.",
            },
        },
        "required": ["query"],
    },
}


class AgentLibToolProvider:
    """AgentLib's 4 navigation tools, calling storage layer directly."""

    def __init__(self, agentlib_data_dir: Path, book_id: str):
        self._data_dir = str(agentlib_data_dir)
        self._book_id = book_id

    @property
    def condition_name(self) -> str:
        return "agentlib"

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            BROWSE_LIBRARY_SCHEMA,
            OPEN_BOOK_SCHEMA,
            READ_CHUNKS_SCHEMA,
            SEARCH_CONCEPTS_SCHEMA,
        ]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        old_val = os.environ.get("AGENTLIB_DATA")
        os.environ["AGENTLIB_DATA"] = self._data_dir
        try:
            return self._dispatch(tool_name, arguments)
        finally:
            if old_val is None:
                os.environ.pop("AGENTLIB_DATA", None)
            else:
                os.environ["AGENTLIB_DATA"] = old_val

    def _dispatch(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        from lib import storage

        if tool_name == "browse_library":
            catalog = storage.read_catalog()
            content = catalog.to_json()
        elif tool_name == "open_book":
            manifest = storage.read_manifest(arguments["book_id"])
            if manifest is None:
                content = json.dumps({"error": f"Book '{arguments['book_id']}' not found"})
            else:
                content = manifest.to_json()
        elif tool_name == "read_chunks":
            chunk_ids = arguments["chunk_ids"][:10]
            chunks = storage.read_chunks(arguments["book_id"], chunk_ids)
            content = json.dumps(chunks, indent=2)
        elif tool_name == "search_concepts":
            results = storage.search_concepts(
                arguments["query"],
                book_id=arguments.get("book_id"),
            )
            content = json.dumps(results, indent=2)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        return ToolResult(content=content, token_estimate=estimate_tokens(content))
