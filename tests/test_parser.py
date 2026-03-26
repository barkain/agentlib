"""Tests for the PDF/EPUB parser — table extraction helpers."""
# ruff: noqa: S101
from __future__ import annotations

from lib.parser import _bboxes_overlap, _table_to_markdown


# ── helpers ───────────────────────────────────────────────────────────────

class _MockTable:
    """Minimal stand-in for a PyMuPDF Table object."""

    def __init__(self, rows: list[list[str | None]], bbox: tuple[float, ...] = (0, 0, 100, 100)):
        self._rows = rows
        self.bbox = bbox

    def extract(self) -> list[list[str | None]]:
        return self._rows


# ── TestBboxesOverlap ─────────────────────────────────────────────────────

class TestBboxesOverlap:
    def test_overlapping(self) -> None:
        assert _bboxes_overlap((0, 0, 50, 50), (25, 25, 75, 75))

    def test_non_overlapping(self) -> None:
        assert not _bboxes_overlap((0, 0, 10, 10), (50, 50, 60, 60))

    def test_contained(self) -> None:
        assert _bboxes_overlap((10, 10, 20, 20), (0, 0, 100, 100))

    def test_slight_overlap(self) -> None:
        # Boxes overlap by 5pt, exceeding the 2pt tolerance
        assert _bboxes_overlap((0, 0, 50, 50), (45, 0, 100, 50))

    def test_edge_outside_tolerance(self) -> None:
        assert not _bboxes_overlap((0, 0, 10, 10), (15, 0, 25, 10))

    def test_above_below(self) -> None:
        assert not _bboxes_overlap((0, 0, 100, 10), (0, 50, 100, 60))


# ── TestTableToMarkdown ──────────────────────────────────────────────────

class TestTableToMarkdown:
    def test_basic_table(self) -> None:
        table = _MockTable([["A", "B"], ["1", "2"], ["3", "4"]])
        md = _table_to_markdown(table)
        assert md == "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"

    def test_none_cells(self) -> None:
        table = _MockTable([["A", "B"], [None, "2"]])
        md = _table_to_markdown(table)
        assert "|  | 2 |" in md

    def test_newlines_flattened(self) -> None:
        table = _MockTable([["Header"], ["line1\nline2"]])
        md = _table_to_markdown(table)
        assert "line1 line2" in md
        assert "\n" not in md.split("\n")[2]  # data row has no embedded newline

    def test_pipe_escaped(self) -> None:
        table = _MockTable([["A"], ["val|ue"]])
        md = _table_to_markdown(table)
        assert "val\\|ue" in md

    def test_empty_table(self) -> None:
        table = _MockTable([])
        assert _table_to_markdown(table) == ""

    def test_empty_header(self) -> None:
        table = _MockTable([[]])
        assert _table_to_markdown(table) == ""

    def test_short_row_padded(self) -> None:
        table = _MockTable([["A", "B", "C"], ["1"]])
        md = _table_to_markdown(table)
        lines = md.split("\n")
        # Data row should have 3 columns like the header
        assert lines[2].count("|") == lines[0].count("|")

    def test_single_column(self) -> None:
        table = _MockTable([["X"], ["a"], ["b"]])
        md = _table_to_markdown(table)
        assert md == "| X |\n| --- |\n| a |\n| b |"

    def test_empty_spacer_columns_stripped(self) -> None:
        """PyMuPDF often detects phantom spacer columns — they should be removed."""
        table = _MockTable([
            ["Phase", None, None, "Description"],
            ["Design", None, None, "Early lifecycle BOM"],
            ["Build", None, None, "Build-time BOM"],
        ])
        md = _table_to_markdown(table)
        assert md == (
            "| Phase | Description |\n"
            "| --- | --- |\n"
            "| Design | Early lifecycle BOM |\n"
            "| Build | Build-time BOM |"
        )
