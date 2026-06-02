"""Fetch arXiv metadata and PDFs.

Parses arXiv IDs from arbitrary URLs, queries the arXiv export API for metadata,
and downloads the PDF — respecting arXiv's User-Agent and rate-limit etiquette.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import httpx

from . import __version__
from .config import Config
from .models import PaperMeta

API_URL = "https://export.arxiv.org/api/query"
PDF_URL_TEMPLATE = "https://arxiv.org/pdf/{id_with_version}.pdf"
ABS_URL_TEMPLATE = "https://arxiv.org/abs/{id_with_version}"

# arXiv API Terms of Use: no more than one request every 3 seconds.
_MIN_REQUEST_INTERVAL = 3.0
_throttle_lock = asyncio.Lock()
_last_request_time = 0.0

# New scheme: YYMM.NNNNN (4-5 digit serial), optional version.
_NEW = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
# Old scheme: archive(.subjectclass)/NNNNNNN (7 digits), optional version.
# The subject class may be uppercase (math.AG) or lowercase with hyphens
# (cond-mat.stat-mech, physics.flu-dyn).
_OLD = re.compile(r"([a-z-]+(?:\.[A-Za-z-]+)?/\d{7})(v\d+)?")


class ArxivError(Exception):
    """Base error for arXiv operations."""


class ArxivNotFound(ArxivError):
    """The requested paper does not exist or was withdrawn."""


def parse_arxiv_id(text: str) -> tuple[str, str | None]:
    """Extract ``(base_id, version)`` from a URL, bare ID, or versioned ID.

    Raises ``ValueError`` if no arXiv ID can be found.
    """
    text = text.strip()
    match = _NEW.search(text) or _OLD.search(text)
    if not match:
        raise ValueError(f"No arXiv ID found in: {text!r}")
    base = match.group(1)
    version = match.group(2)[1:] if match.group(2) else None
    return base, version


def user_agent(cfg: Config) -> str:
    contact = f"; {cfg.user_agent_contact}" if cfg.user_agent_contact else ""
    return (
        f"researcherer/{__version__} "
        f"(+https://github.com/MINERVA-RP/researcherer{contact})"
    )


async def _throttle() -> None:
    """Block until at least ``_MIN_REQUEST_INTERVAL`` has passed since the last hit."""
    global _last_request_time
    async with _throttle_lock:
        wait = _MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_time)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_time = time.monotonic()


def _build_meta(entry, base_id: str, requested_version: str | None) -> PaperMeta:
    # entry.id looks like "http://arxiv.org/abs/2301.12345v2"; recover the version
    # actually served when the caller didn't pin one.
    resolved_version = requested_version
    entry_id = getattr(entry, "id", "") or ""
    vmatch = re.search(r"v(\d+)\s*$", entry_id)
    if vmatch:
        resolved_version = vmatch.group(1)

    authors = [a.get("name", "") for a in getattr(entry, "authors", [])]
    categories = [t.get("term", "") for t in getattr(entry, "tags", []) if t.get("term")]
    primary = ""
    arxiv_primary = getattr(entry, "arxiv_primary_category", None)
    if isinstance(arxiv_primary, dict):
        primary = arxiv_primary.get("term", "")
    if not primary and categories:
        primary = categories[0]

    id_with_version = f"{base_id}v{resolved_version}" if resolved_version else base_id
    return PaperMeta(
        id=base_id,
        version=resolved_version,
        title=" ".join(getattr(entry, "title", "").split()),
        authors=authors,
        abstract=" ".join(getattr(entry, "summary", "").split()),
        categories=categories,
        primary_category=primary,
        source_url=ABS_URL_TEMPLATE.format(id_with_version=id_with_version),
        pdf_url=PDF_URL_TEMPLATE.format(id_with_version=id_with_version),
        pdf_filename=f"{base_id.replace('/', '_')}.pdf",
        published=getattr(entry, "published", ""),
    )


async def fetch_metadata(url_or_id: str, cfg: Config) -> PaperMeta:
    """Resolve an arXiv URL/ID to a :class:`PaperMeta` (no PDF download)."""
    base_id, version = parse_arxiv_id(url_or_id)
    query_id = f"{base_id}v{version}" if version else base_id

    await _throttle()
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(cfg)}, timeout=30.0
    ) as client:
        resp = await client.get(
            API_URL, params={"id_list": query_id, "max_results": 1}
        )
    if resp.status_code == 404:
        raise ArxivNotFound(f"arXiv returned 404 for {query_id}")
    resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    if not feed.entries:
        raise ArxivNotFound(f"No arXiv entry found for {query_id}")

    entry = feed.entries[0]
    title = getattr(entry, "title", "")
    entry_id = getattr(entry, "id", "")
    # arXiv signals bad IDs with a 200 + an "Error" entry.
    if title.strip().lower() == "error" or "api/errors" in entry_id:
        raise ArxivNotFound(f"arXiv reports no such paper: {query_id}")

    return _build_meta(entry, base_id, version)


async def download_pdf(meta: PaperMeta, cfg: Config, dest_dir: Path) -> Path:
    """Download ``meta``'s PDF into ``dest_dir`` atomically. Returns the file path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_path = dest_dir / meta.pdf_filename
    tmp_path = dest_dir / (meta.pdf_filename + ".part")

    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(cfg)},
        timeout=120.0,
        follow_redirects=True,
    ) as client:
        async with client.stream("GET", meta.pdf_url) as resp:
            if resp.status_code == 404:
                raise ArxivNotFound(f"PDF not available for {meta.id_with_version}")
            resp.raise_for_status()
            with tmp_path.open("wb") as fh:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    fh.write(chunk)

    # Validate it is actually a PDF before committing.
    with tmp_path.open("rb") as fh:
        magic = fh.read(5)
    if not magic.startswith(b"%PDF"):
        tmp_path.unlink(missing_ok=True)
        raise ArxivError(
            f"Downloaded file for {meta.id_with_version} is not a PDF "
            f"(starts with {magic!r})"
        )

    tmp_path.replace(final_path)
    return final_path


def now_iso() -> str:
    """Current UTC timestamp in ISO-8601 (``Z`` suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
