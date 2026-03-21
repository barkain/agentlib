"""Book ingestion pipeline: Parse -> Chunk -> Summarise -> Index -> Serialise."""
from __future__ import annotations

import os
from pathlib import Path as _Path


def _load_env() -> None:
    """Load .env file from plugin data directory. Shell env takes precedence."""
    candidates = [
        os.environ.get("CLAUDE_PLUGIN_DATA", ""),
        os.environ.get("AGENTLIB_DATA", ""),
    ]
    for base in candidates:
        if not base:
            continue
        env_path = _Path(base) / ".env"
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

import argparse
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

from lib.chunker import chunk_sections, Chunk
from lib.models import (
    CatalogEntry,
    ChapterInfo,
    ConceptEntry,
    Manifest,
    ParsedSection,
    SectionInfo,
)
from lib.parser import parse_file
from lib.storage import (
    list_chunks,
    read_catalog,
    read_manifest,
    update_catalog_entry,
    write_chunk,
    write_manifest,
)
from lib.summariser import (
    ChapterSummary,
    SectionSummary,
    extract_concepts,
    summarise_book,
    summarise_chapter,
)

logger = logging.getLogger("agentlib.ingest")


def _slugify(name: str) -> str:
    """Convert a filename to a URL-friendly book ID."""
    name = Path(name).stem.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


def _lookup_catalog_summary(book_id: str) -> str:
    """Look up the existing book summary from the catalog."""
    catalog = read_catalog()
    for entry in catalog.books:
        if entry.id == book_id:
            return entry.summary
    return ""


def _group_by_chapter(
    sections: list[ParsedSection],
) -> dict[str, list[ParsedSection]]:
    """Group parsed sections by chapter_id."""
    groups: dict[str, list[ParsedSection]] = defaultdict(list)
    for sec in sections:
        groups[sec.chapter_id].append(sec)
    return dict(groups)


def _group_chunks_by_section(
    chunks: list[Chunk],
) -> dict[str, list[str]]:
    """Map section_id -> list of chunk_ids."""
    result: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        # Extract section from chunk_id: "ch01-s01-001" -> "ch01-s01"
        parts = chunk.chunk_id.rsplit("-", 1)
        if len(parts) == 2:
            section_id = parts[0]
        else:
            section_id = chunk.chunk_id
        result[section_id].append(chunk.chunk_id)
    return dict(result)


def ingest_book(
    file_path: Path,
    book_id: str | None = None,
    force: bool = False,
) -> str:
    """Run the full ingestion pipeline for a book.

    Args:
        file_path: Path to PDF or EPUB file.
        book_id: Optional book identifier. Derived from filename if not given.
        force: If True, re-run all stages even if outputs exist.

    Returns:
        The book_id of the ingested book.
    """
    if book_id is None:
        book_id = _slugify(file_path.name)

    logger.info("Ingesting '%s' as '%s'", file_path.name, book_id)

    # --- Stage 1: Parse ---
    logger.info("Stage 1/5: Parsing...")
    sections = parse_file(file_path)
    logger.info("  Parsed %d sections", len(sections))

    if not sections:
        logger.error("No content extracted from file")
        sys.exit(1)

    # --- Stage 2: Chunk ---
    logger.info("Stage 2/5: Chunking...")
    existing_chunks = list_chunks(book_id) if not force else []

    if existing_chunks and not force:
        logger.info("  Found %d existing chunks, skipping chunking", len(existing_chunks))
        all_chunks: list[Chunk] = []
    else:
        all_chunks = chunk_sections(sections, book_id)
        logger.info("  Created %d chunks", len(all_chunks))

    # --- Stage 3: Write chunks to disk (early, for resumability) ---
    if all_chunks:
        logger.info("Stage 3/5: Writing chunks to disk...")
        for chunk in all_chunks:
            write_chunk(book_id, chunk.chunk_id, chunk.formatted)
        logger.info("  Wrote %d chunk files", len(all_chunks))
    else:
        logger.info("Stage 3/5: Chunks already on disk")

    # Build section->chunks mapping
    if all_chunks:
        section_chunks = _group_chunks_by_section(all_chunks)
    else:
        # Reconstruct from disk
        existing = list_chunks(book_id)
        section_chunks_map: dict[str, list[str]] = defaultdict(list)
        for cid in existing:
            parts = cid.rsplit("-", 1)
            sec_id = parts[0] if len(parts) == 2 else cid
            section_chunks_map[sec_id].append(cid)
        section_chunks = dict(section_chunks_map)

    # --- Stage 4: Summarise ---
    logger.info("Stage 4/5: Summarising chapters...")
    existing_manifest = read_manifest(book_id) if not force else None

    if existing_manifest and not force:
        logger.info("  Manifest exists, skipping summarisation")
        chapter_summaries = [
            ChapterSummary(
                chapter_id=ch.id,
                title=ch.title,
                summary=ch.summary,
                key_concepts=ch.key_concepts,
                sections=[
                    SectionSummary(
                        section_id=sec.id,
                        title=sec.title,
                        summary=sec.summary,
                        chunk_ids=sec.chunk_ids,
                    )
                    for sec in ch.sections
                ],
            )
            for ch in existing_manifest.chapters
        ]
    else:
        chapter_groups = _group_by_chapter(sections)
        chapter_summaries: list[ChapterSummary] = []

        for ch_id, ch_sections in sorted(chapter_groups.items()):
            ch_title = ch_sections[0].chapter_title
            logger.info("  Summarising %s: %s", ch_id, ch_title)

            sec_data = []
            for sec in ch_sections:
                sec_chunk_ids = section_chunks.get(sec.section_id, [])
                sec_data.append({
                    "section_id": sec.section_id,
                    "title": sec.section_title,
                    "text": sec.text,
                    "chunk_ids": sec_chunk_ids,
                })

            summary = summarise_chapter(ch_id, ch_title, sec_data)
            chapter_summaries.append(summary)

        logger.info("  Summarised %d chapters", len(chapter_summaries))

    # --- Stage 5: Index + Serialise ---
    logger.info("Stage 5/5: Building concept index and serialising...")

    if existing_manifest and not force:
        concept_index_raw = existing_manifest.concept_index
        book_summary = _lookup_catalog_summary(book_id)
    else:
        # Extract concepts (1 LLM call)
        concept_mappings = extract_concepts(book_id, chapter_summaries)
        concept_index_raw: dict[str, list[ConceptEntry]] = {}
        for concept, mappings in concept_mappings.items():
            concept_index_raw[concept] = [
                ConceptEntry(ch=m.ch, sec=m.sec, chunks=m.chunks)
                for m in mappings
            ]

        # Book summary (1 LLM call)
        title = file_path.stem.replace("-", " ").replace("_", " ").title()
        book_summary = summarise_book(book_id, title, chapter_summaries)

    # Build manifest
    chapters: list[ChapterInfo] = []
    for ch_sum in chapter_summaries:
        sec_infos = [
            SectionInfo(
                id=sec.section_id,
                title=sec.title,
                summary=sec.summary,
                chunk_ids=sec.chunk_ids,
            )
            for sec in ch_sum.sections
        ]
        chapters.append(ChapterInfo(
            id=ch_sum.chapter_id,
            title=ch_sum.title,
            summary=ch_sum.summary,
            key_concepts=ch_sum.key_concepts,
            sections=sec_infos,
        ))

    manifest = Manifest(
        book_id=book_id,
        chapters=chapters,
        concept_index=concept_index_raw,
    )
    write_manifest(manifest)
    logger.info("  Wrote manifest.json")

    # Update catalog
    total_chunks = sum(
        len(chunk_ids)
        for chunk_ids in section_chunks.values()
    ) if section_chunks else len(list_chunks(book_id))

    title = file_path.stem.replace("-", " ").replace("_", " ").title()
    catalog_entry = CatalogEntry(
        id=book_id,
        title=title,
        domain_tags=[],
        summary=book_summary,
        chapter_count=len(chapters),
        total_chunks=total_chunks,
    )
    update_catalog_entry(catalog_entry)
    logger.info("  Updated catalog.json")

    logger.info(
        "Done! Book '%s' ingested: %d chapters, %d chunks",
        book_id, len(chapters), total_chunks,
    )
    return book_id


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest a book (PDF/EPUB) into the AgentLib library.",
    )
    parser.add_argument("file", type=Path, help="Path to PDF or EPUB file")
    parser.add_argument("--book-id", help="Override book identifier (default: derived from filename)")
    parser.add_argument("--force", action="store_true", help="Re-run all stages even if outputs exist")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not args.file.exists():
        logger.error("File not found: %s", args.file)
        sys.exit(1)

    ingest_book(args.file, book_id=args.book_id, force=args.force)


if __name__ == "__main__":
    main()
