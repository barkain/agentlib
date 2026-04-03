"""Book ingestion pipeline: Parse -> Chunk -> Summarise -> Index -> Serialise."""
from __future__ import annotations

import os
from pathlib import Path as _Path


def _load_env() -> None:
    """Load .env file from plugin data directory. Shell env takes precedence."""
    candidates = [
        os.environ.get("CLAUDE_PLUGIN_DATA", ""),
        os.environ.get("AGENTLIB_DATA", ""),
        str(_Path.home() / ".claude" / "plugins" / "agentlib"),
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
import time
from collections import defaultdict
from pathlib import Path

from lib.chunker import chunk_sections, Chunk
from lib.models import (
    CatalogEntry,
    ChapterInfo,
    ChunkIndex,
    ChunkIndexEntry,
    ConceptEntry,
    LibraryConceptEntry,
    LibraryConceptSource,
    LibraryIndex,
    Manifest,
    ParsedSection,
    PatternEntry,
    PatternIndex,
    SectionInfo,
)
from lib.parser import parse_file
from lib.storage import (
    list_chunks,
    read_catalog,
    read_library_index,
    read_manifest,
    read_pattern_index,
    update_catalog_entry,
    write_chunk,
    write_chunk_index,
    write_compact_manifest,
    write_concept_index,
    write_library_index,
    write_manifest,
    write_navigation_md,
    write_pattern_index,
)
from lib.llm import LLMConfig, detect_provider
from lib.summariser import (
    ChapterSummary,
    SectionSummary,
    extract_concepts,
    summarise_book,
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


def _section_id_from_chunk(chunk_id: str) -> str:
    """Derive section ID from chunk ID (e.g., 'ch01-s01-001' -> 'ch01-s01')."""
    parts = chunk_id.rsplit("-", 1)
    return parts[0] if len(parts) == 2 else chunk_id


def _title_from_path(file_path: Path) -> str:
    """Derive a human-readable title from a file path."""
    return file_path.stem.replace("-", " ").replace("_", " ").title()


def _group_chunks_by_section(
    chunks: list[Chunk],
) -> dict[str, list[str]]:
    """Map section_id -> list of chunk_ids."""
    result: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        result[_section_id_from_chunk(chunk.chunk_id)].append(chunk.chunk_id)
    return dict(result)


def _fuzzy_match_pattern(new_pattern: str, existing_patterns: set[str]) -> str:
    """Match a new pattern to an existing one if similar enough, else return as-is.

    Uses simple Jaccard similarity on character trigrams.
    """
    if new_pattern in existing_patterns:
        return new_pattern

    def _trigrams(s: str) -> set[str]:
        return {s[i:i + 3] for i in range(max(0, len(s) - 2))}

    new_tri = _trigrams(new_pattern)
    if not new_tri:
        return new_pattern

    best_match = new_pattern
    best_score = 0.0
    for existing in existing_patterns:
        existing_tri = _trigrams(existing)
        if not existing_tri:
            continue
        intersection = len(new_tri & existing_tri)
        union = len(new_tri | existing_tri)
        score = intersection / union if union else 0.0
        if score > best_score and score >= 0.7:
            best_score = score
            best_match = existing

    return best_match


def _update_library_indices(book_id: str, manifest: Manifest) -> None:
    """Update library_index.json and pattern_index.json with this book's concepts."""
    source_prefix = f"book:{book_id}"

    # --- Library Index ---
    lib_index = read_library_index()

    # Remove stale entries for this book
    for concept_name, entry in list(lib_index.concepts.items()):
        entry.sources = [s for s in entry.sources if s.source != source_prefix]
        if not entry.sources:
            del lib_index.concepts[concept_name]

    # Merge this book's concepts
    for concept_name, concept_entries in manifest.concept_index.items():
        all_chunks: list[str] = []
        all_aliases: list[str] = []
        all_patterns: list[str] = []
        all_related: list[str] = []
        for ce in concept_entries:
            all_chunks.extend(ce.chunks)
            all_aliases.extend(ce.aliases)
            all_patterns.extend(getattr(ce, "patterns", []))
            all_related.extend(getattr(ce, "related", []))

        source = LibraryConceptSource(source=source_prefix, chunks=all_chunks)

        if concept_name in lib_index.concepts:
            existing = lib_index.concepts[concept_name]
            existing.sources.append(source)
            # Merge aliases/patterns/related with dedup
            existing.aliases = list(dict.fromkeys(existing.aliases + all_aliases))
            existing.patterns = list(dict.fromkeys(existing.patterns + all_patterns))
            existing.related = list(dict.fromkeys(
                r for r in existing.related + all_related if r != concept_name
            ))
        else:
            lib_index.concepts[concept_name] = LibraryConceptEntry(
                sources=[source],
                aliases=list(dict.fromkeys(all_aliases)),
                related=list(dict.fromkeys(r for r in all_related if r != concept_name)),
                patterns=list(dict.fromkeys(all_patterns)),
            )

    write_library_index(lib_index)

    # --- Pattern Index ---
    pat_index = read_pattern_index()
    existing_pattern_names = set(pat_index.patterns.keys())

    # Remove stale entries for this book
    for pattern_name, entries in list(pat_index.patterns.items()):
        pat_index.patterns[pattern_name] = [
            e for e in entries if e.source != source_prefix
        ]
        if not pat_index.patterns[pattern_name]:
            del pat_index.patterns[pattern_name]
            existing_pattern_names.discard(pattern_name)

    # Add new pattern entries with fuzzy merge
    for concept_name, concept_entries in manifest.concept_index.items():
        all_chunks: list[str] = []
        raw_patterns: list[str] = []
        for ce in concept_entries:
            all_chunks.extend(ce.chunks)
            raw_patterns.extend(getattr(ce, "patterns", []))

        unique_patterns = list(dict.fromkeys(raw_patterns))
        for raw_pat in unique_patterns:
            canonical = _fuzzy_match_pattern(raw_pat, existing_pattern_names)
            if canonical not in pat_index.patterns:
                pat_index.patterns[canonical] = []
            pat_index.patterns[canonical].append(PatternEntry(
                concept=concept_name,
                source=source_prefix,
                chunks=all_chunks,
            ))
            existing_pattern_names.add(canonical)

    write_pattern_index(pat_index)


def ingest_book(
    file_path: Path,
    book_id: str | None = None,
    force: bool = False,
    llm_config: LLMConfig | None = None,
) -> str:
    """Run the full ingestion pipeline for a book.

    Args:
        file_path: Path to PDF or EPUB file.
        book_id: Optional book identifier. Derived from filename if not given.
        force: If True, re-run all stages even if outputs exist.
        llm_config: LLM provider config. Auto-detected if None.

    Returns:
        The book_id of the ingested book.
    """
    if llm_config is None:
        llm_config = detect_provider()
    logger.info("Using LLM provider: %s (%s)", llm_config.provider, llm_config.model)
    if book_id is None:
        book_id = _slugify(file_path.name)

    logger.info("Ingesting '%s' as '%s'", file_path.name, book_id)

    # --- Stage 1: Parse ---
    logger.info("Stage 1/5: Parsing...")
    sections, extracted_images = parse_file(file_path)
    logger.info("  Parsed %d sections", len(sections))

    # Write extracted images to disk
    if extracted_images:
        from lib.storage import write_image
        for img_filename, img_bytes in extracted_images.items():
            write_image(book_id, img_filename, img_bytes)
        logger.info("  Extracted %d images", len(extracted_images))

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
            section_chunks_map[_section_id_from_chunk(cid)].append(cid)
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

        # Determine concurrency from env (default 10)
        try:
            concurrency = max(1, int(os.environ.get("AGENTLIB_CONCURRENCY", "10")))
        except (ValueError, TypeError):
            concurrency = 10

        import asyncio
        from lib.summariser import async_summarise_chapter

        async def _summarise_all() -> list[ChapterSummary]:
            sem = asyncio.Semaphore(concurrency)
            tasks = []

            for ch_id, ch_sections in sorted(chapter_groups.items()):
                ch_title = ch_sections[0].chapter_title

                sec_data = []
                for sec in ch_sections:
                    sec_chunk_ids = section_chunks.get(sec.section_id, [])
                    sec_data.append({
                        "section_id": sec.section_id,
                        "title": sec.section_title,
                        "text": sec.text,
                        "chunk_ids": sec_chunk_ids,
                    })

                # Collect images for this chapter
                ch_images: list[tuple[str, str]] | None = None
                ch_image_files: list[str] = []
                for sec in ch_sections:
                    ch_image_files.extend(sec.images)
                if ch_image_files:
                    from lib.storage import read_image_base64
                    ch_images = []
                    for img_file in ch_image_files:
                        try:
                            b64, mt = read_image_base64(book_id, img_file)
                            ch_images.append((b64, mt))
                        except FileNotFoundError:
                            continue
                    if not ch_images:
                        ch_images = None

                MAX_CHAPTER_IMAGES = 5
                if ch_images and len(ch_images) > MAX_CHAPTER_IMAGES:
                    ch_images = ch_images[:MAX_CHAPTER_IMAGES]

                tasks.append(async_summarise_chapter(
                    ch_id, ch_title, sec_data,
                    llm_config=llm_config, images=ch_images,
                    semaphore=sem,
                ))

            logger.info("  Summarising %d chapters (concurrency=%d)...", len(tasks), concurrency)
            return list(await asyncio.gather(*tasks))

        chapter_summaries = asyncio.run(_summarise_all())

        logger.info("  Summarised %d chapters", len(chapter_summaries))

        # Save manifest early (with empty concept index) so stage 4 can be
        # skipped on retry if stage 5 fails.
        chapters_for_manifest: list[ChapterInfo] = []
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
            chapters_for_manifest.append(ChapterInfo(
                id=ch_sum.chapter_id,
                title=ch_sum.title,
                summary=ch_sum.summary,
                key_concepts=ch_sum.key_concepts,
                sections=sec_infos,
            ))
        partial_manifest = Manifest(
            book_id=book_id,
            chapters=chapters_for_manifest,
            concept_index={},
        )
        write_manifest(partial_manifest)
        logger.info("  Saved partial manifest (stages 1-4 recoverable)")

    # --- Stage 5: Index + Serialise ---
    logger.info("Stage 5/5: Building concept index and serialising...")

    existing_in_catalog = bool(_lookup_catalog_summary(book_id))
    if existing_manifest and existing_in_catalog and not force:
        concept_index_raw = existing_manifest.concept_index
        book_summary = _lookup_catalog_summary(book_id)
    else:
        # Extract concepts (batched LLM calls for large books)
        max_retries = 3
        concept_mappings: dict | None = None
        for attempt in range(1, max_retries + 1):
            try:
                concept_mappings = extract_concepts(book_id, chapter_summaries, llm_config=llm_config)
                break
            except (RuntimeError, TypeError, AttributeError, ValueError) as e:
                if attempt < max_retries:
                    logger.warning("Concept extraction failed (attempt %d/%d): %s", attempt, max_retries, e)
                    logger.info("  Retrying in 30 seconds...")
                    time.sleep(30)
                else:
                    logger.error("Concept extraction failed after %d attempts: %s", max_retries, e)
                    logger.error("Stages 1-4 completed. Retry with the same command.")
                    raise
        if concept_mappings is None:  # pragma: no cover – loop always breaks or raises
            raise RuntimeError("Concept extraction produced no result")

        # Post-process: fill in missing chunk_ids from section_chunks mapping
        # Pre-build chapter lookup for fallback
        chapter_chunks: dict[str, list[str]] = defaultdict(list)
        for sec_id, cids in section_chunks.items():
            ch_id = sec_id.split("-")[0] if "-" in sec_id else sec_id
            chapter_chunks[ch_id].extend(cids)

        for concept, mappings in concept_mappings.items():
            for m in mappings:
                if not m.chunks:
                    # Look up chunk_ids from section_chunks mapping
                    sec_chunks = section_chunks.get(m.sec, [])
                    if sec_chunks:
                        m.chunks = sec_chunks
                    elif m.ch:
                        # Fallback: find any chunks for this chapter
                        ch_chunks = chapter_chunks.get(m.ch, [])[:3]
                        if ch_chunks:
                            m.chunks = ch_chunks  # Cap at 3 to keep index compact

        concept_index_raw: dict[str, list[ConceptEntry]] = {}
        for concept, mappings in concept_mappings.items():
            concept_index_raw[concept] = [
                ConceptEntry(ch=m.ch, sec=m.sec, chunks=m.chunks, aliases=m.aliases)
                for m in mappings
            ]

        # Book summary (1 LLM call)
        title = _title_from_path(file_path)
        book_summary = summarise_book(book_id, title, chapter_summaries, llm_config=llm_config)

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

    # Write zero-server navigation files
    write_compact_manifest(manifest)
    logger.info("  Wrote manifest.compact.json")
    write_concept_index(book_id, manifest.concept_index)
    logger.info("  Wrote concepts.json")

    # Build chunk_index.json — per-book preview metadata for smart navigation
    chunk_idx_entries: dict[str, ChunkIndexEntry] = {}
    # Build concept->chunk reverse map
    chunk_concepts: dict[str, list[str]] = defaultdict(list)
    for concept_name, entries in manifest.concept_index.items():
        for entry in entries:
            for cid in entry.chunks:
                if concept_name not in chunk_concepts[cid]:
                    chunk_concepts[cid].append(concept_name)

    # Build section label map from manifest
    section_labels: dict[str, str] = {}
    for ch in manifest.chapters:
        for sec in ch.sections:
            for cid in sec.chunk_ids:
                section_labels[cid] = f"{ch.title} > {sec.title}"

    # Populate chunk index with prev/next from written chunks
    all_chunk_ids = list_chunks(book_id)
    for cid in all_chunk_ids:
        chunk_idx_entries[cid] = ChunkIndexEntry(
            section=section_labels.get(cid, ""),
            concepts=chunk_concepts.get(cid, []),
            tokens=0,  # filled below if available
        )

    # Set prev/next chains per section group and token counts
    sec_groups: dict[str, list[str]] = defaultdict(list)
    for cid in all_chunk_ids:
        sec_id = _section_id_from_chunk(cid)
        sec_groups[sec_id].append(cid)
    for sec_id, cids in sec_groups.items():
        for i, cid in enumerate(cids):
            entry = chunk_idx_entries[cid]
            if i > 0:
                entry.prev = cids[i - 1]
            if i < len(cids) - 1:
                entry.next = cids[i + 1]

    # Get token counts from the chunks we just created
    if all_chunks:
        for chunk in all_chunks:
            if chunk.chunk_id in chunk_idx_entries:
                chunk_idx_entries[chunk.chunk_id].tokens = chunk.meta.token_count

    chunk_index = ChunkIndex(book_id=book_id, chunks=chunk_idx_entries)
    write_chunk_index(book_id, chunk_index)
    logger.info("  Wrote chunk_index.json (%d entries)", len(chunk_idx_entries))

    # Update unified library_index.json and pattern_index.json
    _update_library_indices(book_id, manifest)
    logger.info("  Updated library_index.json and pattern_index.json")

    # Update catalog
    total_chunks = sum(
        len(chunk_ids)
        for chunk_ids in section_chunks.values()
    ) if section_chunks else len(list_chunks(book_id))

    title = _title_from_path(file_path)
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

    # Regenerate NAVIGATION.md with updated library listing
    write_navigation_md()
    logger.info("  Wrote NAVIGATION.md")

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
