"""The top-level Textual application."""

from __future__ import annotations

from textual.app import App

from ..config import Config
from .screens.library import LibraryScreen


class ResearchererApp(App):
    """Fetch and read arXiv papers in the terminal."""

    CSS_PATH = "app.tcss"
    TITLE = "researcherer"
    SUB_TITLE = "arXiv paper reader"
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.cfg = config

    def on_mount(self) -> None:
        self.push_screen(LibraryScreen(self.cfg))
