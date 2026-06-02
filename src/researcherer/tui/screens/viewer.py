"""The PDF viewer screen: page nav, zoom, image/text toggle, and search."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from ... import library
from ...config import Config
from ...models import PaperMeta
from ...pdf import PdfDocument, SearchMatch
from ...render import (
    PageRenderer,
    active_renderer_name,
    graphics_protocol_available,
)
from ..widgets.page_view import PageView

_DPI_STEP = 25
_DPI_MIN = 50
_DPI_MAX = 600


class PageReady(Message):
    """A page has finished rendering off the UI thread."""

    def __init__(
        self,
        index: int,
        mode: str,
        image=None,
        text: str | None = None,
        error: str | None = None,
    ) -> None:
        super().__init__()
        self.index = index
        self.mode = mode
        self.image = image
        self.text = text
        self.error = error


class SearchDone(Message):
    def __init__(self, needle: str, matches: list[SearchMatch]) -> None:
        super().__init__()
        self.needle = needle
        self.matches = matches


class ViewerScreen(Screen):
    """Render a single PDF with navigation, zoom, mode toggle, and search."""

    BINDINGS = [
        Binding("right,space,pagedown", "next_page", "Next"),
        Binding("left,pageup", "prev_page", "Prev"),
        Binding("down", "scroll_down", "Scroll ↓", show=False),
        Binding("up", "scroll_up", "Scroll ↑", show=False),
        Binding("g", "first_page", "First", show=False),
        Binding("G", "last_page", "Last", show=False),
        Binding("plus,equals_sign", "zoom_in", "Zoom +"),
        Binding("minus", "zoom_out", "Zoom -"),
        Binding("t", "toggle_mode", "Img/Txt"),
        Binding("slash", "search", "Search"),
        Binding("n", "next_match", "Next match", show=False),
        Binding("N", "prev_match", "Prev match", show=False),
        Binding("escape,q", "back", "Back"),
    ]

    def __init__(self, meta: PaperMeta, cfg: Config) -> None:
        super().__init__()
        self.meta = meta
        self.cfg = cfg
        self.doc: PdfDocument | None = None
        self.renderer: PageRenderer | None = None
        self.page_index = 0
        self.dpi = cfg.default_dpi
        self.mode = "image"
        self.has_text = True
        self.matches: list[SearchMatch] = []
        self.match_pos = -1

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="viewer-banner", classes="-hidden")
        yield PageView()
        yield Input(placeholder="Search… (Enter to find, Esc to cancel)",
                    id="search-input", classes="-hidden")
        yield Static("", id="viewer-status")
        yield Footer()

    # ---- lifecycle ----

    def on_mount(self) -> None:
        pdf_file = library.pdf_path(self.meta, self.cfg)
        try:
            self.doc = PdfDocument(pdf_file)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Could not open PDF: {exc}", severity="error")
            self.app.pop_screen()
            return
        if self.doc.page_count == 0:
            self.notify("This PDF has no pages.", severity="error")
            self.app.pop_screen()
            return

        self.renderer = PageRenderer(self.doc)
        self.has_text = self.doc.has_extractable_text()
        self.renderer_name = active_renderer_name()
        self.mode = self._initial_mode()
        self.sub_title = self.meta.title or self.meta.id_with_version
        self._update_banner()
        # Keep the (hidden) search box out of the focus chain so navigation keys
        # reach the screen; it is made focusable only while searching.
        self.query_one("#search-input", Input).can_focus = False
        self.set_focus(None)
        self._show_page()

    def on_unmount(self) -> None:
        if self.doc is not None:
            self.doc.close()

    def _initial_mode(self) -> str:
        if self.cfg.image_mode == "text":
            return "text" if self.has_text else "image"
        if self.cfg.image_mode == "image":
            return "image"
        # auto
        if graphics_protocol_available():
            return "image"
        return "text" if self.has_text else "image"

    def _update_banner(self) -> None:
        """Show the most relevant warning, or hide the banner."""
        banner = self.query_one("#viewer-banner", Static)
        message = ""
        if self.mode == "image" and self.renderer_name in ("halfcell", "unicode", "none"):
            message = (
                "This terminal has no image protocol — page images are low-res. "
                "Press 't' for sharp text, or use Kitty / iTerm2 / WezTerm / Ghostty."
            )
        elif not self.has_text and self.mode == "text":
            message = "No extractable text (scanned PDF) — press 't' for image mode."
        if message:
            banner.update(message)
            banner.remove_class("-hidden")
        else:
            banner.add_class("-hidden")

    # ---- rendering ----

    def _show_page(self) -> None:
        if self.doc is None or self.renderer is None:
            return
        self._render_worker(self.page_index, self.mode)
        self._update_status()

    @work(thread=True, exclusive=True, group="render")
    def _render_worker(self, index: int, mode: str) -> None:
        assert self.doc is not None and self.renderer is not None
        try:
            if mode == "image":
                image = self.renderer.render(index, self.dpi)
                self.post_message(PageReady(index, mode, image=image))
            else:
                text = self.doc.page_text(index)
                self.post_message(PageReady(index, mode, text=text))
        except Exception as exc:  # noqa: BLE001
            self.post_message(PageReady(index, mode, error=str(exc)))

    async def on_page_ready(self, message: PageReady) -> None:
        # Drop stale renders (user navigated or toggled mode meanwhile).
        if message.index != self.page_index or message.mode != self.mode:
            return
        page_view = self.query_one(PageView)
        if message.error:
            self.notify(f"Render error: {message.error}", severity="error")
            return
        if message.image is not None:
            await page_view.show_image(message.image)
        else:
            await page_view.show_text(message.text or "")
        self._update_status()

    def _update_status(self) -> None:
        if self.doc is None:
            return
        parts = [f"Page {self.page_index + 1}/{self.doc.page_count}", self.mode.upper()]
        if self.mode == "image":
            parts.append(f"{self.dpi} dpi")
            parts.append(self.renderer_name)
        if self.matches:
            parts.append(f"match {self.match_pos + 1}/{len(self.matches)}")
        parts.append(self.meta.id_with_version)
        self.query_one("#viewer-status", Static).update("   |   ".join(parts))

    # ---- navigation actions ----

    def action_next_page(self) -> None:
        if self.doc and self.page_index < self.doc.page_count - 1:
            self.page_index += 1
            self._show_page()

    def action_prev_page(self) -> None:
        if self.page_index > 0:
            self.page_index -= 1
            self._show_page()

    def action_first_page(self) -> None:
        if self.page_index != 0:
            self.page_index = 0
            self._show_page()

    def action_last_page(self) -> None:
        if self.doc and self.page_index != self.doc.page_count - 1:
            self.page_index = self.doc.page_count - 1
            self._show_page()

    def action_scroll_down(self) -> None:
        self.query_one(PageView).scroll_page(down=True)

    def action_scroll_up(self) -> None:
        self.query_one(PageView).scroll_page(down=False)

    # ---- zoom & mode ----

    def action_zoom_in(self) -> None:
        if self.mode != "image":
            return
        new = min(self.dpi + _DPI_STEP, _DPI_MAX)
        if new != self.dpi:
            self.dpi = new
            self._show_page()

    def action_zoom_out(self) -> None:
        if self.mode != "image":
            return
        new = max(self.dpi - _DPI_STEP, _DPI_MIN)
        if new != self.dpi:
            self.dpi = new
            self._show_page()

    def action_toggle_mode(self) -> None:
        self.mode = "text" if self.mode == "image" else "image"
        if self.mode == "text" and not self.has_text:
            self.notify("No extractable text in this PDF.", severity="warning")
        self._update_banner()
        self._show_page()

    # ---- search ----

    def action_search(self) -> None:
        search = self.query_one("#search-input", Input)
        search.can_focus = True
        search.remove_class("-hidden")
        search.focus()

    def _hide_search(self) -> None:
        search = self.query_one("#search-input", Input)
        search.value = ""
        search.add_class("-hidden")
        search.can_focus = False
        self.set_focus(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search-input":
            return
        needle = event.value.strip()
        search = self.query_one("#search-input", Input)
        search.add_class("-hidden")
        search.can_focus = False
        self.set_focus(None)
        if needle:
            self.notify(f"Searching for “{needle}” …")
            self._search_worker(needle)

    @work(thread=True, exclusive=True, group="search")
    def _search_worker(self, needle: str) -> None:
        assert self.doc is not None
        try:
            matches = self.doc.search(needle)
        except Exception as exc:  # noqa: BLE001
            self.post_message(SearchDone(needle, []))
            self.notify(f"Search failed: {exc}", severity="error")
            return
        self.post_message(SearchDone(needle, matches))

    def on_search_done(self, message: SearchDone) -> None:
        self.matches = message.matches
        if not self.matches:
            self.match_pos = -1
            self.notify(f"No matches for “{message.needle}”.", severity="warning")
            self._update_status()
            return
        self.match_pos = 0
        self.notify(f"{len(self.matches)} match(es) for “{message.needle}”.")
        self._goto_match()

    def _goto_match(self) -> None:
        if not self.matches:
            return
        target = self.matches[self.match_pos].page
        if target != self.page_index:
            self.page_index = target
            self._show_page()
        else:
            self._update_status()

    def action_next_match(self) -> None:
        if not self.matches:
            return
        self.match_pos = (self.match_pos + 1) % len(self.matches)
        self._goto_match()

    def action_prev_match(self) -> None:
        if not self.matches:
            return
        self.match_pos = (self.match_pos - 1) % len(self.matches)
        self._goto_match()

    # ---- exit ----

    def action_back(self) -> None:
        search = self.query_one("#search-input", Input)
        if not search.has_class("-hidden"):
            self._hide_search()
            return
        self.app.pop_screen()
