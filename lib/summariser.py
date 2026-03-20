"""Haiku-based summarisation: chapter summaries + concept extraction."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic


DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _get_client() -> anthropic.Anthropic:
    """Get Anthropic client. API key from environment."""
    return anthropic.Anthropic()


@dataclass
class SectionSummary:
    """Summary output for a single section."""
    section_id: str
    title: str
    summary: str
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ChapterSummary:
    """Summary output for a single chapter."""
    chapter_id: str
    title: str
    summary: str
    key_concepts: list[str] = field(default_factory=list)
    sections: list[SectionSummary] = field(default_factory=list)


@dataclass
class ConceptMapping:
    """A concept mapped to its locations."""
    concept: str
    ch: str
    sec: str
    chunks: list[str] = field(default_factory=list)


def summarise_chapter(
    chapter_id: str,
    chapter_title: str,
    sections: list[dict],
    model: str = DEFAULT_MODEL,
) -> ChapterSummary:
    """Summarise a single chapter using Haiku.

    Args:
        chapter_id: Chapter identifier (e.g., "ch01").
        chapter_title: Chapter title.
        sections: List of dicts with keys: section_id, title, text, chunk_ids.
        model: Anthropic model to use.

    Returns:
        ChapterSummary with chapter and section summaries + key concepts.
    """
    client = _get_client()

    sections_text = ""
    for sec in sections:
        sections_text += f"\n### {sec['title']} (ID: {sec['section_id']})\n"
        sections_text += f"Chunk IDs: {', '.join(sec.get('chunk_ids', []))}\n"
        # Truncate section text to avoid token limits
        text = sec.get("text", "")
        if len(text) > 3000:
            text = text[:3000] + "... [truncated]"
        sections_text += text + "\n"

    prompt = f"""Analyze this chapter and produce a JSON response.

## Chapter: {chapter_title} (ID: {chapter_id})

{sections_text}

Respond with ONLY valid JSON in this exact format:
{{
  "chapter_summary": "1-2 sentence summary of the chapter",
  "key_concepts": ["concept1", "concept2", ...],
  "section_summaries": [
    {{"section_id": "...", "title": "...", "summary": "1 sentence summary"}}
  ]
}}

Key concepts should be specific, searchable terms (3-5 per chapter). Section summaries should be concise (1 sentence each)."""

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.content[0].text.strip()
    # Extract JSON from response (handle markdown code blocks)
    if result_text.startswith("```"):
        lines = result_text.split("\n")
        result_text = "\n".join(lines[1:-1])

    data = json.loads(result_text)

    section_summaries = []
    for sec_data in data.get("section_summaries", []):
        # Find matching chunk_ids from input
        matching_chunks = []
        for sec in sections:
            if sec["section_id"] == sec_data.get("section_id"):
                matching_chunks = sec.get("chunk_ids", [])
                break
        section_summaries.append(SectionSummary(
            section_id=sec_data.get("section_id", ""),
            title=sec_data.get("title", ""),
            summary=sec_data.get("summary", ""),
            chunk_ids=matching_chunks,
        ))

    return ChapterSummary(
        chapter_id=chapter_id,
        title=chapter_title,
        summary=data.get("chapter_summary", ""),
        key_concepts=data.get("key_concepts", []),
        sections=section_summaries,
    )


def extract_concepts(
    book_id: str,
    chapter_summaries: list[ChapterSummary],
    model: str = DEFAULT_MODEL,
) -> dict[str, list[ConceptMapping]]:
    """Extract a concept index for the entire book using Haiku.

    One LLM call. Given all chapter summaries and their key concepts,
    produces a unified concept index.

    Returns:
        Dict mapping concept name -> list of ConceptMapping.
    """
    client = _get_client()

    chapters_text = ""
    for ch in chapter_summaries:
        chapters_text += f"\n## {ch.title} (ID: {ch.chapter_id})\n"
        chapters_text += f"Summary: {ch.summary}\n"
        chapters_text += f"Key concepts: {', '.join(ch.key_concepts)}\n"
        for sec in ch.sections:
            chapters_text += f"  - {sec.title} (ID: {sec.section_id}): {sec.summary}\n"
            chapters_text += f"    Chunks: {', '.join(sec.chunk_ids)}\n"

    prompt = f"""Given these chapter summaries for book "{book_id}", create a unified concept index.

{chapters_text}

Create a concept index that maps key concepts to their locations. Each concept should appear with all relevant chapters, sections, and chunks where it's discussed.

Respond with ONLY valid JSON in this exact format:
{{
  "concept_name_1": [
    {{"ch": "ch01", "sec": "ch01-s01", "chunks": ["ch01-s01-001", "ch01-s01-002"]}}
  ],
  "concept_name_2": [
    {{"ch": "ch02", "sec": "ch02-s03", "chunks": ["ch02-s03-001"]}}
  ]
}}

Include 20-50 concepts. Use specific, searchable terms. Merge similar concepts."""

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.content[0].text.strip()
    if result_text.startswith("```"):
        lines = result_text.split("\n")
        result_text = "\n".join(lines[1:-1])

    data = json.loads(result_text)

    concept_index: dict[str, list[ConceptMapping]] = {}
    for concept, entries in data.items():
        concept_index[concept] = [
            ConceptMapping(
                concept=concept,
                ch=e.get("ch", ""),
                sec=e.get("sec", ""),
                chunks=e.get("chunks", []),
            )
            for e in entries
        ]

    return concept_index


def summarise_book(
    book_id: str,
    title: str,
    chapter_summaries: list[ChapterSummary],
    model: str = DEFAULT_MODEL,
) -> str:
    """Generate a 1-2 sentence book summary from chapter summaries.

    Returns:
        Book summary string.
    """
    client = _get_client()

    chapters_text = "\n".join(
        f"- {ch.title}: {ch.summary}" for ch in chapter_summaries
    )

    prompt = f"""Given these chapter summaries for "{title}":

{chapters_text}

Write a 1-2 sentence summary of the entire book. Be specific about what it covers and its main purpose. Respond with ONLY the summary text, nothing else."""

    response = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()
