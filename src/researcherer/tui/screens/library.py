"""The library screen: browse fetched papers and fetch new ones."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from ... import library
from ...config import Config
from ...models import PaperMeta
from .dialogs import ConfirmModal, FetchModal


class LibraryScreen(Screen):
    """A table of all fetched papers with fetch / open / delete actions."""

    BINDINGS = [
        Binding("f", "fetch", "Fetch"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "delete", "Delete"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self._papers: list[PaperMeta] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="library-table", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("ID", "Title", "Authors", "Fetched")
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._papers = library.list_papers(self.cfg)
        for meta in self._papers:
            authors = ", ".join(meta.authors[:3])
            if len(meta.authors) > 3:
                authors += ", …"
            table.add_row(
                meta.id_with_version,
                meta.title or "(untitled)",
                authors,
                (meta.fetched_at or "")[:10],
            )
        if self._papers:
            self.sub_title = f"{len(self._papers)} paper(s)"
        else:
            self.sub_title = "no papers yet — press 'f' to fetch one"

    # ---- actions ----

    def action_refresh(self) -> None:
        self.refresh_table()

    def action_fetch(self) -> None:
        def _on_url(url: str | None) -> None:
            if url:
                self._fetch(url)

        self.app.push_screen(FetchModal(), _on_url)

    def _selected(self) -> PaperMeta | None:
        table = self.query_one(DataTable)
        idx = table.cursor_row
        if idx is None or not (0 <= idx < len(self._papers)):
            return None
        return self._papers[idx]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._open_selected()

    def _open_selected(self) -> None:
        meta = self._selected()
        if meta is None:
            return
        if not library.pdf_path(meta, self.cfg).exists():
            self.notify("PDF file is missing for this paper.", severity="error")
            return
        from .viewer import ViewerScreen

        self.app.push_screen(ViewerScreen(meta, self.cfg))

    def action_delete(self) -> None:
        meta = self._selected()
        if meta is None:
            return

        def _on_confirm(confirmed: bool) -> None:
            if confirmed:
                library.delete_paper(meta, self.cfg)
                self.notify(f"Deleted {meta.id_with_version}")
                self.refresh_table()

        self.app.push_screen(
            ConfirmModal(f"Delete {meta.id_with_version} and its files?"),
            _on_confirm,
        )

    @work(exclusive=True)
    async def _fetch(self, url: str) -> None:
        self.notify(f"Fetching {url} …")
        try:
            meta = await library.fetch_paper(url, self.cfg)
        except Exception as exc:  # noqa: BLE001 - present any failure to the user
            self.notify(f"Fetch failed: {exc}", severity="error", timeout=8)
            return
        self.notify(
            f"Saved {meta.id_with_version}: {meta.title}",
            severity="information",
            timeout=6,
        )
        self.refresh_table()
