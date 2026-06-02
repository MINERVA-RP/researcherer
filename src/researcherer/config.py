"""Configuration loading and default paths."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

APP_NAME = "researcherer"

VALID_IMAGE_MODES = ("auto", "image", "text")

_DEFAULT_CONFIG_TEMPLATE = """\
# researcherer configuration
library_dir = "~/researcherer/papers"   # where fetched papers are stored
default_dpi = 200                         # page render resolution (zoom); raise for sharper pages
image_mode = "auto"                       # auto | image | text
user_agent_contact = ""                   # optional email/URL added to the User-Agent
"""


@dataclass
class Config:
    library_dir: Path = field(default_factory=lambda: Path("~/researcherer/papers"))
    default_dpi: int = 200
    image_mode: str = "auto"
    user_agent_contact: str = ""

    def __post_init__(self) -> None:
        self.library_dir = Path(self.library_dir).expanduser()
        if self.image_mode not in VALID_IMAGE_MODES:
            self.image_mode = "auto"
        self.default_dpi = max(50, min(int(self.default_dpi), 600))


def config_search_paths() -> list[Path]:
    """Ordered candidate locations for ``config.toml`` (first existing wins)."""
    paths: list[Path] = []
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        paths.append(Path(xdg) / APP_NAME / "config.toml")
    paths.append(Path.home() / ".config" / APP_NAME / "config.toml")
    paths.append(Path(platformdirs.user_config_dir(APP_NAME)) / "config.toml")
    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def default_config_path() -> Path:
    """Where a fresh template config is written if none exists."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_NAME / "config.toml"


def load_config() -> Config:
    """Load configuration, writing a default template if none is found."""
    for path in config_search_paths():
        if path.is_file():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except (tomllib.TOMLDecodeError, OSError):
                data = {}
            return Config(
                library_dir=data.get("library_dir", "~/researcherer/papers"),
                default_dpi=data.get("default_dpi", 200),
                image_mode=data.get("image_mode", "auto"),
                user_agent_contact=data.get("user_agent_contact", ""),
            )

    # No config found: write a template (best effort) and use defaults.
    try:
        target = default_config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(_DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    except OSError:
        pass
    return Config()
