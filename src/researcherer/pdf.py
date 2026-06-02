"""A thin wrapper over PyMuPDF providing the operations the TUI needs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class SearchMatch:
    page: int  # 0-based page index
    rect: tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points


class PdfDocument:
    """Open a PDF and expose page rendering, text, and search."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._doc = pymupdf.open(self.path)

    def close(self) -> None:
        self._doc.close()

    def __enter__(self) -> PdfDocument:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    @property
    def title(self) -> str:
        return (self._doc.metadata or {}).get("title", "") or ""

    def render_page_png(self, index: int, dpi: int = 150) -> bytes:
        """Render page ``index`` to PNG bytes at the given DPI."""
        page = self._doc.load_page(self._clamp(index))
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")

    def page_text(self, index: int) -> str:
        """Plain-text content of page ``index`` (empty for scanned pages)."""
        page = self._doc.load_page(self._clamp(index))
        return page.get_text("text")

    def has_extractable_text(self, sample_pages: int = 3) -> bool:
        """Heuristic: does this PDF have any extractable text in early pages?"""
        for i in range(min(sample_pages, self.page_count)):
            if self.page_text(i).strip():
                return True
        return False

    def search(self, needle: str) -> list[SearchMatch]:
        """Find ``needle`` across all pages, returning ordered matches."""
        needle = needle.strip()
        if not needle:
            return []
        matches: list[SearchMatch] = []
        for i in range(self.page_count):
            page = self._doc.load_page(i)
            for rect in page.search_for(needle):
                matches.append(
                    SearchMatch(page=i, rect=(rect.x0, rect.y0, rect.x1, rect.y1))
                )
        return matches

    def outline(self) -> list[tuple[int, str, int]]:
        """Table of contents as ``(level, title, page_number)`` (1-based pages)."""
        return [tuple(item) for item in self._doc.get_toc()]

    def _clamp(self, index: int) -> int:
        if self.page_count == 0:
            raise IndexError("PDF has no pages")
        return max(0, min(index, self.page_count - 1))
