"""On-disk library of fetched papers.

Each paper lives in ``<library_dir>/<folder_name>/`` containing the PDF and a
``metadata.json`` file.
"""

from __future__ import annotations

from pathlib import Path

from . import arxiv
from .config import Config
from .models import PaperMeta

METADATA_FILENAME = "metadata.json"


def paper_dir(meta: PaperMeta, cfg: Config) -> Path:
    return cfg.library_dir / meta.folder_name


def metadata_path(meta: PaperMeta, cfg: Config) -> Path:
    return paper_dir(meta, cfg) / METADATA_FILENAME


def pdf_path(meta: PaperMeta, cfg: Config) -> Path:
    return paper_dir(meta, cfg) / meta.pdf_filename


def save_metadata(meta: PaperMeta, cfg: Config) -> Path:
    """Write ``metadata.json`` for ``meta`` and return its path."""
    directory = paper_dir(meta, cfg)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / METADATA_FILENAME
    path.write_text(meta.to_json(), encoding="utf-8")
    return path


def list_papers(cfg: Config) -> list[PaperMeta]:
    """Return every paper in the library, newest fetch first.

    Malformed ``metadata.json`` files are skipped rather than raising.
    """
    if not cfg.library_dir.is_dir():
        return []
    papers: list[PaperMeta] = []
    for meta_file in cfg.library_dir.glob(f"*/{METADATA_FILENAME}"):
        try:
            papers.append(PaperMeta.load(meta_file))
        except (ValueError, OSError, KeyError):
            continue
    papers.sort(key=lambda p: p.fetched_at, reverse=True)
    return papers


def delete_paper(meta: PaperMeta, cfg: Config) -> None:
    """Remove a paper's folder and all its contents."""
    directory = paper_dir(meta, cfg)
    if not directory.is_dir():
        return
    for child in sorted(directory.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            child.rmdir()
    directory.rmdir()


async def fetch_paper(url_or_id: str, cfg: Config) -> PaperMeta:
    """Full fetch pipeline: metadata -> PDF download -> persist metadata.

    The PDF is downloaded first; ``metadata.json`` is written only after both
    succeed, so a failed fetch never leaves a half-populated folder behind.
    """
    meta = await arxiv.fetch_metadata(url_or_id, cfg)
    directory = paper_dir(meta, cfg)
    await arxiv.download_pdf(meta, cfg, directory)
    meta.fetched_at = arxiv.now_iso()
    save_metadata(meta, cfg)
    return meta
