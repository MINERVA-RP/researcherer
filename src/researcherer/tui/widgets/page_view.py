"""A container that displays the current page as either an image or text."""

from __future__ import annotations

from textual.containers import Container, VerticalScroll
from textual.widgets import Static


class PageView(Container):
    """Swaps between a rendered page image and extracted page text."""

    def __init__(self) -> None:
        super().__init__(id="page-view")

    async def show_image(self, pil_image) -> None:
        # Imported lazily: textual-image probes the terminal on first use, so we
        # avoid importing it unless an image is actually displayed.
        from textual_image.widget import Image

        await self.remove_children()
        await self.mount(Image(pil_image, id="page-image"))

    async def show_text(self, text: str) -> None:
        await self.remove_children()
        body = text if text.strip() else "(no extractable text on this page)"
        scroll = VerticalScroll(Static(body, id="page-text"))
        # The screen owns navigation/scroll bindings; keep this container out of
        # the focus chain so arrow keys reach the screen (and the search input
        # still receives keys normally when it is focused).
        scroll.can_focus = False
        await self.mount(scroll)

    def scroll_page(self, *, down: bool) -> None:
        """Scroll the text container, if one is showing."""
        for scroll in self.query(VerticalScroll):
            if down:
                scroll.scroll_down()
            else:
                scroll.scroll_up()
            return
