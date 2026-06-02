"""Exercise the real PyMuPDF engine against a generated one-page PDF."""

import pymupdf

from researcherer.pdf import PdfDocument
from researcherer.render import PageRenderer


def _make_pdf(path, text="Hello transformer world"):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=14)
    doc.save(path)
    doc.close()


def test_page_count_and_text(tmp_path):
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    with PdfDocument(pdf) as doc:
        assert doc.page_count == 1
        assert "transformer" in doc.page_text(0)
        assert doc.has_extractable_text()


def test_search_returns_positions(tmp_path):
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    with PdfDocument(pdf) as doc:
        matches = doc.search("transformer")
        assert matches, "expected at least one match"
        assert matches[0].page == 0
        x0, y0, x1, y1 = matches[0].rect
        assert x1 > x0 and y1 > y0

        assert doc.search("definitely-not-present") == []


def test_render_png_and_cache(tmp_path):
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)
    with PdfDocument(pdf) as doc:
        png = doc.render_page_png(0, dpi=100)
        assert png[:4] == b"\x89PNG"

        renderer = PageRenderer(doc)
        first = renderer.render(0, 100)
        second = renderer.render(0, 100)
        assert first is second  # served from cache
        assert first.width > 0 and first.height > 0
