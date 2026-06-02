"""Data models for papers and their on-disk metadata."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class PaperMeta:
    """Metadata describing a single fetched arXiv paper.

    ``id`` is the canonical arXiv identifier (e.g. ``2301.12345`` or
    ``math/0309136``). ``folder_name`` is the filesystem-safe form used as the
    directory name (old-style IDs replace ``/`` with ``_``).
    """

    id: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    categories: list[str] = field(default_factory=list)
    primary_category: str = ""
    version: str | None = None
    source_url: str = ""
    pdf_url: str = ""
    pdf_filename: str = ""
    published: str = ""
    fetched_at: str = ""
    schema_version: int = SCHEMA_VERSION

    @property
    def folder_name(self) -> str:
        """Filesystem-safe directory name for this paper."""
        return self.id.replace("/", "_")

    @property
    def id_with_version(self) -> str:
        """Canonical id with version suffix if known (e.g. ``2301.12345v2``)."""
        return f"{self.id}v{self.version}" if self.version else self.id

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> PaperMeta:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def load(cls, path: Path) -> PaperMeta:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
