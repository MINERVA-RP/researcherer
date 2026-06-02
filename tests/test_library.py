"""Library persistence: metadata round-trip, listing, folder naming, delete."""

from researcherer import library
from researcherer.config import Config
from researcherer.models import PaperMeta


def _cfg(tmp_path):
    return Config(library_dir=tmp_path)


def _meta(**kw):
    base = dict(
        id="2301.12345",
        title="A Test Paper",
        authors=["Ada Lovelace", "Alan Turing"],
        abstract="An abstract.",
        categories=["cs.AI"],
        primary_category="cs.AI",
        version="2",
        pdf_filename="2301.12345.pdf",
        fetched_at="2026-06-02T10:00:00Z",
    )
    base.update(kw)
    return PaperMeta(**base)


def test_metadata_round_trip(tmp_path):
    cfg = _cfg(tmp_path)
    meta = _meta()
    path = library.save_metadata(meta, cfg)
    assert path.exists()
    loaded = PaperMeta.load(path)
    assert loaded == meta


def test_old_style_id_folder_naming(tmp_path):
    cfg = _cfg(tmp_path)
    meta = _meta(id="math/0309136", pdf_filename="math_0309136.pdf")
    library.save_metadata(meta, cfg)
    assert (tmp_path / "math_0309136" / "metadata.json").exists()
    # The canonical id with the slash is preserved inside the metadata.
    assert PaperMeta.load(tmp_path / "math_0309136" / "metadata.json").id == "math/0309136"


def test_list_papers_sorted_and_tolerant(tmp_path):
    cfg = _cfg(tmp_path)
    library.save_metadata(_meta(id="2301.00001", fetched_at="2026-01-01T00:00:00Z"), cfg)
    library.save_metadata(_meta(id="2301.00002", fetched_at="2026-05-01T00:00:00Z"), cfg)
    # A malformed metadata file should be skipped, not crash listing.
    bad = tmp_path / "broken"
    bad.mkdir()
    (bad / "metadata.json").write_text("{ not json", encoding="utf-8")

    papers = library.list_papers(cfg)
    assert [p.id for p in papers] == ["2301.00002", "2301.00001"]  # newest first


def test_delete_paper(tmp_path):
    cfg = _cfg(tmp_path)
    meta = _meta()
    library.save_metadata(meta, cfg)
    library.pdf_path(meta, cfg).write_bytes(b"%PDF-1.4 fake")
    assert library.paper_dir(meta, cfg).exists()

    library.delete_paper(meta, cfg)
    assert not library.paper_dir(meta, cfg).exists()
