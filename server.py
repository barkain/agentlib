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

# ---------------------------------------------------------------------------
# Token budget constants & helpers
# ---------------------------------------------------------------------------
MAX_SUMMARY_CHARS = 80
MAX_CHAPTER_SUMMARY_CHARS = 100
MAX_CONCEPTS_PER_CHAPTER = 3
MAX_SEARCH_RESULTS = 10
MAX_MANIFEST_CHARS = 8000  # ~2000 tokens
MAX_MANIFEST_CHAPTERS = 20


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


@mcp.tool()
def browse_library() -> str:
    """List all books in the library with titles, summaries, and chapter/chunk counts."""
    catalog = storage.read_catalog()
    compact_books = []
    for b in catalog.books:
        compact_books.append({
            "id": b.id,
            "title": b.title,
            "summary": _truncate(b.summary, MAX_SUMMARY_CHARS),
            "chapters": b.chapter_count,
            "chunks": b.total_chunks,
        })
    return json.dumps({"books": compact_books})


@mcp.tool()
def open_book(book_id: str) -> str:
    """Get detailed chapter and section structure for a specific book, including summaries and concept index."""
    if not storage.book_exists(book_id):
        return json.dumps({"error": f"Book not found: {book_id}"})
    manifest = storage.read_manifest(book_id)
    if manifest is None:
        return json.dumps({"error": f"Manifest not found for book: {book_id}"})

    chapters = []
    for ch in manifest.chapters:
        chapters.append({
            "id": ch.id,
            "title": ch.title,
            "summary": _truncate(ch.summary, MAX_CHAPTER_SUMMARY_CHARS),
            "concepts": ch.key_concepts[:MAX_CONCEPTS_PER_CHAPTER],
            "sections": len(ch.sections),
            "chunks": sum(len(s.chunk_ids) for s in ch.sections),
        })

    compact: dict = {"book_id": manifest.book_id}

    # Truncate chapters if too many
    if len(chapters) > MAX_MANIFEST_CHAPTERS:
        compact["chapters"] = chapters[:MAX_MANIFEST_CHAPTERS]
        compact["note"] = f"Showing first {MAX_MANIFEST_CHAPTERS} of {len(chapters)} chapters"
    else:
        compact["chapters"] = chapters

    # Concept index: flat list of concept names only
    compact["concepts"] = sorted(manifest.concept_index.keys())

    result = json.dumps(compact)

    # Final safety check on total size
    if len(result) > MAX_MANIFEST_CHARS:
        # Re-truncate chapters until we fit
        while len(compact["chapters"]) > 1:
            compact["chapters"] = compact["chapters"][:len(compact["chapters"]) - 1]
            compact["note"] = f"Showing first {len(compact['chapters'])} of {len(chapters)} chapters (truncated for size)"
            result = json.dumps(compact)
            if len(result) <= MAX_MANIFEST_CHARS:
                break

    return result


@mcp.tool()
def read_chunks(book_id: str, chunk_ids: list[str]) -> str:
    """Read the full content of specific chunks by ID. Max 10 chunks per call."""
    if len(chunk_ids) > 10:
        return json.dumps({"error": "Maximum 10 chunk IDs per call."})
    chunks = storage.read_chunks(book_id, chunk_ids)
    return json.dumps(chunks, indent=2)


@mcp.tool()
def search_concepts(query: str, book_id: str | None = None) -> str:
    """Search for concepts across all books (or a specific book). Returns matching concept names with their chunk locations."""
    if book_id and not storage.book_exists(book_id):
        return json.dumps({"error": f"Book not found: {book_id}"})
    results = storage.search_concepts(query, book_id=book_id)

    # Flatten to concept -> chunk_ids and cap at MAX_SEARCH_RESULTS
    compact: dict = {}
    truncated = False
    for concept_key, entries in results.items():
        if len(compact) >= MAX_SEARCH_RESULTS:
            truncated = True
            break
        compact[concept_key] = [
            cid for entry in entries for cid in entry["chunks"]
        ]

    if truncated:
        compact["truncated"] = True  # type: ignore[assignment]

    return json.dumps(compact)


if __name__ == "__main__":
    mcp.run()
