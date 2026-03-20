"""Filesystem I/O layer for AgentLib data storage."""
from __future__ import annotations

import os
from pathlib import Path

from lib.models import Catalog, CatalogEntry, Manifest


def _data_root() -> Path:
    """Resolve the data root directory."""
    env = os.environ.get("AGENTLIB_DATA")
    if env:
        return Path(env)
    return Path.home() / ".agentlib" / "library"


def _books_root() -> Path:
    return _data_root() / "books"


# ---------------------------------------------------------------------------
# Catalog (L0)
# ---------------------------------------------------------------------------

def read_catalog() -> Catalog:
    """Read the library catalog. Returns empty catalog if not found."""
    path = _books_root() / "catalog.json"
    if not path.exists():
        return Catalog()
    return Catalog.from_json(path.read_text(encoding="utf-8"))


def write_catalog(catalog: Catalog) -> Path:
    """Write the library catalog to disk."""
    path = _books_root() / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(catalog.to_json(), encoding="utf-8")
    return path


def update_catalog_entry(entry: CatalogEntry) -> Catalog:
    """Add or update a single book in the catalog."""
    catalog = read_catalog()
    for i, existing in enumerate(catalog.books):
        if existing.id == entry.id:
            catalog.books[i] = entry
            write_catalog(catalog)
            return catalog
    catalog.books.append(entry)
    write_catalog(catalog)
    return catalog


# ---------------------------------------------------------------------------
# Manifest (L1)
# ---------------------------------------------------------------------------

def read_manifest(book_id: str) -> Manifest | None:
    """Read a book manifest. Returns None if not found."""
    path = _books_root() / book_id / "manifest.json"
    if not path.exists():
        return None
    return Manifest.from_json(path.read_text(encoding="utf-8"))


def write_manifest(manifest: Manifest) -> Path:
    """Write a book manifest to disk."""
    path = _books_root() / manifest.book_id / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.to_json(), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Chunks (L2)
# ---------------------------------------------------------------------------

def _chunk_dir(book_id: str) -> Path:
    return _books_root() / book_id / "chunks"


def read_chunk(book_id: str, chunk_id: str) -> str | None:
    """Read a single chunk file. Returns None if not found."""
    path = _chunk_dir(book_id) / f"{chunk_id}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def read_chunks(book_id: str, chunk_ids: list[str]) -> dict[str, str | None]:
    """Read multiple chunks. Returns dict of chunk_id -> content (None if missing)."""
    return {cid: read_chunk(book_id, cid) for cid in chunk_ids}


def write_chunk(book_id: str, chunk_id: str, content: str) -> Path:
    """Write a single chunk file to disk."""
    chunk_dir = _chunk_dir(book_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    path = chunk_dir / f"{chunk_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


def list_chunks(book_id: str) -> list[str]:
    """List all chunk IDs for a book."""
    chunk_dir = _chunk_dir(book_id)
    if not chunk_dir.exists():
        return []
    return sorted(p.stem for p in chunk_dir.glob("*.md"))


def book_exists(book_id: str) -> bool:
    """Check if a book directory exists."""
    return (_books_root() / book_id).is_dir()


def book_dir(book_id: str) -> Path:
    """Return the path to a book's directory."""
    return _books_root() / book_id


# ---------------------------------------------------------------------------
# Concept search (Ls)
# ---------------------------------------------------------------------------

def search_concepts(query: str, book_id: str | None = None) -> dict[str, list[dict]]:
    """Search concept index across books. Substring match on concept names.

    Returns dict of concept_name -> list of {ch, sec, chunks} entries.
    If book_id is specified, search only that book.
    """
    results: dict[str, list[dict]] = {}
    query_lower = query.lower()

    if book_id:
        book_ids = [book_id]
    else:
        catalog = read_catalog()
        book_ids = [b.id for b in catalog.books]

    for bid in book_ids:
        manifest = read_manifest(bid)
        if manifest is None:
            continue
        for concept, entries in manifest.concept_index.items():
            if query_lower in concept.lower():
                key = f"{bid}:{concept}"
                results[key] = [
                    {"ch": e.ch, "sec": e.sec, "chunks": e.chunks}
                    for e in entries
                ]

    return results
