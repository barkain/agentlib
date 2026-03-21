"""PDF and EPUB parsing into ParsedSection objects."""
from __future__ import annotations

import html.parser
import re
from collections import Counter
from pathlib import Path

from lib.models import ParsedSection


# ---------------------------------------------------------------------------
# PDF Parsing (PyMuPDF)
# ---------------------------------------------------------------------------

def parse_pdf(path: Path) -> list[ParsedSection]:
    """Parse a PDF file into sections using PyMuPDF."""
    import fitz  # type: ignore[import-untyped]  # PyMuPDF

    doc = fitz.open(str(path))
    sections: list[ParsedSection] = []

    # --- Detect font sizes for heading classification ---
    size_counter: Counter[float] = Counter()
    for pn in range(len(doc)):
        page_dict = doc[pn].get_text("dict")
        for blk in page_dict.get("blocks", []):
            if blk.get("type") != 0:
                continue
            for ln in blk.get("lines", []):
                for span in ln.get("spans", []):
                    txt = span["text"].strip()
                    if txt and len(txt) > 3:
                        size = round(span["size"], 1)
                        size_counter[size] += len(txt)

    if size_counter:
        body_size = size_counter.most_common(1)[0][0]
        # Pick the two most-used font sizes larger than body text.
        # Sort by character count descending so that the real heading
        # sizes (used many times) win over rare cover-page sizes.
        heading_sizes = sorted(
            [(s, size_counter[s]) for s in size_counter if s > body_size + 0.5],
            key=lambda x: x[1],
            reverse=True,
        )
        if len(heading_sizes) >= 2:
            # Two most-used heading sizes; smaller = section, larger = chapter
            top_two = sorted([heading_sizes[0][0], heading_sizes[1][0]])
            section_thresh = top_two[0]
            chapter_thresh = top_two[1]
        elif len(heading_sizes) == 1:
            section_thresh = heading_sizes[0][0]
            chapter_thresh = heading_sizes[0][0]
        else:
            section_thresh = body_size + 2.0
            chapter_thresh = body_size + 4.0
    else:
        body_size, section_thresh, chapter_thresh = 10.0, 12.0, 14.0

    # --- State for section accumulation ---
    current_chapter_num = 1
    current_section_num = 1
    current_chapter_title = "Introduction"
    current_section_title = "Main"
    current_text_parts: list[str] = []
    current_page_start: int | None = None
    current_page_end: int | None = None

    def _flush_section() -> None:
        nonlocal current_text_parts, current_page_start, current_page_end
        text = "\n".join(current_text_parts).strip()
        if text:
            ch_id = f"ch{current_chapter_num:02d}"
            sec_id = f"{ch_id}-s{current_section_num:02d}"
            sections.append(ParsedSection(
                chapter_id=ch_id,
                chapter_title=current_chapter_title,
                section_id=sec_id,
                section_title=current_section_title,
                text=text,
                page_start=current_page_start,
                page_end=current_page_end,
            ))
        current_text_parts = []
        current_page_start = None
        current_page_end = None

    def _is_heading(block_text: str, font_size: float = 0.0) -> tuple[bool, str]:
        """Heuristic heading detection. Returns (is_heading, level)."""
        line = block_text.strip()
        if not line or len(line) > 100:
            return False, ""

        # --- Text-pattern-based detection ---

        # Chapter patterns
        if re.match(r"^(Chapter|CHAPTER)\s+\d+", line):
            return True, "chapter"
        if re.match(r"^(Part|PART)\s+[IVXLCDM\d]+", line):
            return True, "chapter"

        # Top-level numbered headings like "1 Title" (LaTeX \section)
        if (
            re.match(r"^\d+\s+[A-Z]\S", line)
            and not re.match(r"^\d+\.\d+", line)
            and len(line) < 80
        ):
            return True, "chapter"

        # Sub-section patterns: "1.1 Title" or "1.1.1 Title"
        if re.match(r"^\d+(\.\d+)+\s+\S", line) and len(line) < 80:
            return True, "section"

        # ALL CAPS short lines (likely headings) with at least 2 words
        if line.isupper() and len(line) < 60 and len(line.split()) >= 2:
            return True, "section"

        # --- Font-size-based detection ---
        if font_size > 0 and len(line) < 80:
            if font_size >= chapter_thresh and chapter_thresh > section_thresh:
                return True, "chapter"
            if font_size >= section_thresh and font_size > body_size + 0.5:
                return True, "section"

        return False, ""

    # --- Main loop over pages and blocks ---
    page_dict_cache: dict[int, dict] = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")

        # Get dict representation for font-size lookup
        if page_num not in page_dict_cache:
            page_dict_cache[page_num] = page.get_text("dict")
        pg_dict = page_dict_cache[page_num]

        for block in blocks:
            if block[6] != 0:  # Skip image blocks
                continue
            text = block[4].strip()
            if not text:
                continue

            # Determine font size of this block via bbox matching
            _x0, by0, _x1, by1 = block[:4]
            font_size = 0.0
            for dict_block in pg_dict.get("blocks", []):
                if dict_block.get("type") != 0:
                    continue
                db = dict_block["bbox"]
                if abs(db[1] - by0) < 2 and abs(db[3] - by1) < 2:
                    for ln in dict_block.get("lines", []):
                        for span in ln.get("spans", []):
                            if span["text"].strip():
                                font_size = max(font_size, span["size"])
                    break
            font_size = round(font_size, 1)

            is_heading, level = _is_heading(text, font_size)

            if is_heading and level == "chapter":
                _flush_section()
                current_chapter_num += 1
                current_section_num = 1
                current_chapter_title = text.strip()
                current_section_title = "Main"
                current_page_start = page_num + 1
                current_page_end = page_num + 1
            elif is_heading and level == "section":
                _flush_section()
                current_section_num += 1
                current_section_title = text.strip()
                current_page_start = page_num + 1
                current_page_end = page_num + 1
            else:
                current_text_parts.append(text)
                if current_page_start is None:
                    current_page_start = page_num + 1
                current_page_end = page_num + 1

    _flush_section()

    # If no sections were created, create a single section with all text
    # NOTE: doc must still be open here for the fallback to work
    if not sections:
        full_text = "\n".join(
            block[4].strip()
            for pn in range(len(doc))
            for block in doc[pn].get_text("blocks")
            if block[6] == 0 and block[4].strip()
        )
        if full_text:
            sections.append(ParsedSection(
                chapter_id="ch01",
                chapter_title=Path(path).stem,
                section_id="ch01-s01",
                section_title="Full Content",
                text=full_text,
                page_start=1,
                page_end=len(doc),
            ))

    doc.close()

    return sections


# ---------------------------------------------------------------------------
# EPUB Parsing (ebooklib)
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(html.parser.HTMLParser):
    """Simple HTML to text converter that tracks headings."""

    HEADING_TAGS = {"h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[dict] = []  # {"type": "heading"|"text", "level": int, "text": str}
        self._current_tag: str = ""
        self._current_text: list[str] = []
        self._in_heading = False
        self._heading_level = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._current_tag = tag
        if tag in self.HEADING_TAGS:
            # Flush current text
            self._flush_text()
            self._in_heading = True
            self._heading_level = int(tag[1])
            self._current_text = []
        elif tag in ("p", "div", "br", "li"):
            self._current_text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.HEADING_TAGS and self._in_heading:
            heading_text = "".join(self._current_text).strip()
            if heading_text:
                self.parts.append({
                    "type": "heading",
                    "level": self._heading_level,
                    "text": heading_text,
                })
            self._in_heading = False
            self._current_text = []
        elif tag in ("p", "div"):
            self._current_text.append("\n\n")

    def handle_data(self, data: str) -> None:
        self._current_text.append(data)

    def _flush_text(self) -> None:
        text = "".join(self._current_text).strip()
        if text:
            self.parts.append({"type": "text", "level": 0, "text": text})
        self._current_text = []

    def close(self) -> None:
        super().close()
        self._flush_text()


def parse_epub(path: Path) -> list[ParsedSection]:
    """Parse an EPUB file into sections using ebooklib."""
    import ebooklib  # type: ignore[import-untyped]
    from ebooklib import epub  # type: ignore[import-untyped]

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    sections: list[ParsedSection] = []

    chapter_num = 1
    section_num = 1
    current_chapter_title = "Introduction"

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        content = item.get_content().decode("utf-8", errors="replace")

        extractor = _HTMLTextExtractor()
        extractor.feed(content)
        extractor.close()

        if not extractor.parts:
            continue

        current_text_parts: list[str] = []
        current_section_title = "Main"

        def flush_section() -> None:
            nonlocal section_num
            text = "\n\n".join(current_text_parts).strip()
            if text:
                ch_id = f"ch{chapter_num:02d}"
                sec_id = f"{ch_id}-s{section_num:02d}"
                sections.append(ParsedSection(
                    chapter_id=ch_id,
                    chapter_title=current_chapter_title,
                    section_id=sec_id,
                    section_title=current_section_title,
                    text=text,
                ))

        for part in extractor.parts:
            if part["type"] == "heading":
                if part["level"] <= 1:
                    # Chapter heading
                    flush_section()
                    current_text_parts = []
                    chapter_num += 1
                    section_num = 1
                    current_chapter_title = part["text"]
                    current_section_title = "Main"
                else:
                    # Section heading
                    flush_section()
                    current_text_parts = []
                    section_num += 1
                    current_section_title = part["text"]
            else:
                current_text_parts.append(part["text"])

        flush_section()
        current_text_parts = []

    # Fallback if no structure detected
    if not sections and chapter_num == 0:
        chapter_num = 1
        section_num = 1
        all_text = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = item.get_content().decode("utf-8", errors="replace")
            extractor = _HTMLTextExtractor()
            extractor.feed(content)
            extractor.close()
            for part in extractor.parts:
                if part["type"] == "text":
                    all_text.append(part["text"])
        if all_text:
            sections.append(ParsedSection(
                chapter_id="ch01",
                chapter_title=Path(path).stem,
                section_id="ch01-s01",
                section_title="Full Content",
                text="\n\n".join(all_text),
            ))

    return sections


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def parse_file(path: Path) -> list[ParsedSection]:
    """Parse a PDF or EPUB file into sections."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    elif suffix == ".epub":
        return parse_epub(path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Supported: .pdf, .epub")
