"""Paper metadata extraction from PDF first pages."""
from __future__ import annotations

import json
import re
from pathlib import Path

from lib.llm import LLMConfig, call_llm, detect_provider


def extract_metadata(
    pdf_path: Path,
    llm_config: LLMConfig | None = None,
) -> dict:
    """Extract metadata from a scientific paper PDF.

    Returns a dict with keys: title, authors, year, venue, abstract, keywords, page_count.
    Uses LLM to parse the first 1-2 pages.
    """
    import fitz  # type: ignore[import-untyped]

    config = llm_config or detect_provider()
    doc = fitz.open(str(pdf_path))

    # Get first 2 pages text
    text = ""
    for i in range(min(2, len(doc))):
        text += doc[i].get_text()
    page_count = len(doc)
    doc.close()

    # Truncate to ~3000 chars to stay within token limits
    text = text[:3000]

    prompt = f"""Extract metadata from this scientific paper's first pages. Return ONLY valid JSON.

<paper_content>
{text}
</paper_content>

Return:
{{"title": "full paper title", "authors": ["Author Name 1", "Author Name 2"], "year": 2024, "venue": "journal or conference or empty string", "abstract": "the full abstract text", "keywords": ["keyword1", "keyword2", "keyword3"]}}"""

    result = call_llm(config, prompt, max_tokens=1024)

    # Strip markdown code fences if present
    if result.startswith("```"):
        lines = result.split("\n")
        result = "\n".join(lines[1:-1])

    # Remove trailing commas before } or ] (common LLM mistake)
    result = re.sub(r",\s*([}\]])", r"\1", result)

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        # Try to find the outermost JSON object
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(result[start:end])
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    data["page_count"] = page_count

    # Fill defaults
    if "title" not in data or not data["title"]:
        data["title"] = pdf_path.stem
    if "authors" not in data:
        data["authors"] = []
    if "year" not in data:
        data["year"] = _extract_year_from_filename(pdf_path.name)
    if "venue" not in data:
        data["venue"] = ""
    if "abstract" not in data:
        data["abstract"] = ""
    if "keywords" not in data:
        data["keywords"] = []

    return data


def slugify_paper(title: str, authors: list[str], year: int | None) -> str:
    """Generate a paper ID like 'davidson2019-planck-area'."""
    # First author surname
    author_part = ""
    if authors:
        surname = authors[0].split()[-1].lower()
        author_part = re.sub(r"[^a-z]", "", surname)

    year_part = str(year) if year else "nd"

    # First few words of title
    title_words = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()[:3]
    title_part = "-".join(title_words)

    slug = f"{author_part}{year_part}-{title_part}"
    # Ensure it starts with alphanumeric and is safe for paths
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    if not slug or not slug[0].isalnum():
        slug = "paper-" + slug
    return slug


def _extract_year_from_filename(filename: str) -> int | None:
    """Extract year from arXiv ID in filename (YYMM.NNNNN)."""
    match = re.search(r"(\d{2})(\d{2})\.\d{4,5}", filename)
    if match:
        yy = int(match.group(1))
        year = 2000 + yy if yy < 50 else 1900 + yy
        return year
    # Try a 4-digit year
    match = re.search(r"(19|20)\d{2}", filename)
    if match:
        return int(match.group(0))
    return None
