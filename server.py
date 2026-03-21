"""AgentLib MCP server — book-domain knowledge navigation tools."""
from __future__ import annotations

import os
from pathlib import Path


def _load_env() -> None:
    """Load .env file from plugin data directory. Shell env takes precedence."""
    candidates = [
        os.environ.get("CLAUDE_PLUGIN_DATA", ""),
        os.environ.get("AGENTLIB_DATA", ""),
        str(Path.home() / ".claude" / "plugins" / "agentlib"),
    ]
    for base in candidates:
        if not base:
            continue
        env_path = Path(base) / ".env"
        if env_path.exists():
            try:
                env_path.chmod(0o600)
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()
                        if key and os.environ.get(key) is None:
                            os.environ[key] = value
            except OSError:
                pass
            return


_load_env()

import json

from fastmcp import FastMCP

from lib import storage

mcp = FastMCP("agentlib")


@mcp.tool()
def browse_library() -> str:
    """List all books in the library with titles, tags, summaries, and chapter/chunk counts."""
    catalog = storage.read_catalog()
    return catalog.to_json()


@mcp.tool()
def open_book(book_id: str) -> str:
    """Get detailed chapter and section structure for a specific book, including summaries and concept index."""
    if not storage.book_exists(book_id):
        return json.dumps({"error": f"Book not found: {book_id}"})
    manifest = storage.read_manifest(book_id)
    if manifest is None:
        return json.dumps({"error": f"Manifest not found for book: {book_id}"})
    return manifest.to_json()


@mcp.tool()
def read_chunks(book_id: str, chunk_ids: list[str]) -> str:
    """Read the full content of specific chunks by ID. Max 10 chunks per call."""
    if len(chunk_ids) > 10:
        return json.dumps({"error": "Maximum 10 chunk IDs per call."})
    chunks = storage.read_chunks(book_id, chunk_ids)
    return json.dumps(chunks, indent=2)


@mcp.tool()
def search_concepts(query: str, book_id: str | None = None) -> str:
    """Search for concepts across all books (or a specific book). Returns matching concept names with their chapter, section, and chunk locations."""
    if book_id and not storage.book_exists(book_id):
        return json.dumps({"error": f"Book not found: {book_id}"})
    results = storage.search_concepts(query, book_id=book_id)
    return json.dumps(results, indent=2)


if __name__ == "__main__":
    mcp.run()
