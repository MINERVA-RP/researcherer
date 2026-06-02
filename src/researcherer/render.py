"""Page rendering helpers: PNG caching and terminal-capability detection.

The actual terminal image protocol selection (Kitty / Sixel / unicode) is handled
by ``textual-image``; this module decides whether to show images at all and caches
rendered pages so navigation stays snappy.
"""

from __future__ import annotations

import io
from collections import OrderedDict

from PIL import Image as PILImage

from .pdf import PdfDocument

_MAX_CACHED_PAGES = 16


class PageRenderer:
    """Render PDF pages to PIL images with a small LRU cache."""

    def __init__(self, doc: PdfDocument, max_cached: int = _MAX_CACHED_PAGES) -> None:
        self.doc = doc
        self._cache: OrderedDict[tuple[int, int], PILImage.Image] = OrderedDict()
        self._max_cached = max_cached

    def render(self, index: int, dpi: int) -> PILImage.Image:
        key = (index, dpi)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        png = self.doc.render_page_png(index, dpi=dpi)
        image = PILImage.open(io.BytesIO(png))
        image.load()
        self._cache[key] = image
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cached:
            self._cache.popitem(last=False)
        return image

    def clear(self) -> None:
        self._cache.clear()


def prime_terminal_detection() -> None:
    """Trigger ``textual-image``'s terminal capability + cell-size detection.

    This MUST be called before the Textual app starts: ``textual-image`` probes
    the terminal with escape sequences and can no longer do so once Textual's
    input loop owns stdin. Calling it early is what lets capable terminals use a
    real graphics protocol (Kitty/Sixel) instead of the blocky halfcell fallback,
    and gives the renderer the true cell pixel size so pages stay sharp.
    """
    try:
        import textual_image.widget  # noqa: F401  (import side effect: detection)
    except Exception:
        pass


def active_renderer_name() -> str:
    """Name of the renderer ``textual-image`` selected for this terminal.

    One of ``"sixel"``, ``"tgp"``, ``"halfcell"``, ``"unicode"``, or ``"none"``.
    Only ``sixel``/``tgp`` are true pixel-graphics protocols; the others are
    character-cell approximations that look blocky for dense content.
    """
    try:
        from textual_image.renderable import Image as Auto
        from textual_image.renderable.halfcell import Image as Halfcell
        from textual_image.renderable.sixel import Image as Sixel
        from textual_image.renderable.tgp import Image as TGP
        from textual_image.renderable.unicode import Image as Unicode
    except Exception:
        return "none"
    return {
        Sixel: "sixel",
        TGP: "tgp",
        Halfcell: "halfcell",
        Unicode: "unicode",
    }.get(Auto, "unknown")


def graphics_protocol_available() -> bool:
    """True only when a real pixel-graphics protocol (Kitty/Sixel) is active.

    Influences the *default* mode in ``image_mode = "auto"``: with a true graphics
    protocol we lean toward crisp page images, otherwise toward legible text. The
    user can always toggle with ``t``.
    """
    return active_renderer_name() in ("sixel", "tgp")
