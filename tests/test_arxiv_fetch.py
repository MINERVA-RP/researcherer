"""Fetch pipeline with mocked HTTP (no real network)."""

import httpx
import pytest
import respx

from researcherer import arxiv, library
from researcherer.config import Config

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <published>2017-06-12T17:57:34Z</published>
    <title>Attention Is All You Need</title>
    <summary>  The dominant sequence transduction models are based on
    recurrent or convolutional neural networks.  </summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <arxiv:primary_category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""

ERROR_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format</id>
    <title>Error</title>
    <summary>incorrect id format for 9999.99999</summary>
  </entry>
</feed>
"""


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    # Keep the test fast and deterministic.
    monkeypatch.setattr(arxiv, "_MIN_REQUEST_INTERVAL", 0.0)
    monkeypatch.setattr(arxiv, "_last_request_time", 0.0)


@respx.mock
async def test_fetch_metadata_parses_fields():
    respx.get(url__regex=r"export\.arxiv\.org/api/query").mock(
        return_value=httpx.Response(200, text=ATOM)
    )
    cfg = Config()
    meta = await arxiv.fetch_metadata("https://arxiv.org/abs/1706.03762", cfg)
    assert meta.id == "1706.03762"
    assert meta.version == "7"  # resolved from the entry id
    assert meta.title == "Attention Is All You Need"
    assert meta.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert "cs.CL" in meta.categories and "cs.LG" in meta.categories
    assert meta.pdf_url.endswith("1706.03762v7.pdf")


@respx.mock
async def test_fetch_metadata_not_found():
    respx.get(url__regex=r"export\.arxiv\.org/api/query").mock(
        return_value=httpx.Response(200, text=ERROR_ATOM)
    )
    with pytest.raises(arxiv.ArxivNotFound):
        await arxiv.fetch_metadata("9999.99999", Config())


@respx.mock
async def test_full_fetch_pipeline_writes_files(tmp_path):
    respx.get(url__regex=r"export\.arxiv\.org/api/query").mock(
        return_value=httpx.Response(200, text=ATOM)
    )
    respx.get(url__regex=r"arxiv\.org/pdf/.*\.pdf").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.4\nfake body\n%%EOF")
    )
    cfg = Config(library_dir=tmp_path)
    meta = await library.fetch_paper("https://arxiv.org/abs/1706.03762", cfg)

    paper_dir = library.paper_dir(meta, cfg)
    assert (paper_dir / "metadata.json").exists()
    assert library.pdf_path(meta, cfg).read_bytes().startswith(b"%PDF")
    assert meta.fetched_at  # stamped during the pipeline


@respx.mock
async def test_rejects_non_pdf_download(tmp_path):
    respx.get(url__regex=r"export\.arxiv\.org/api/query").mock(
        return_value=httpx.Response(200, text=ATOM)
    )
    respx.get(url__regex=r"arxiv\.org/pdf/.*\.pdf").mock(
        return_value=httpx.Response(200, content=b"<html>not a pdf</html>")
    )
    cfg = Config(library_dir=tmp_path)
    with pytest.raises(arxiv.ArxivError):
        await library.fetch_paper("https://arxiv.org/abs/1706.03762", cfg)
