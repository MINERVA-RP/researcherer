"""Small modal dialogs (fetch URL prompt, confirm)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class FetchModal(ModalScreen[str | None]):
    """Prompt for an arXiv URL/ID. Dismisses with the entered value or ``None``."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="fetch-dialog"):
            yield Label("Paste an arXiv URL or ID:")
            yield Input(
                placeholder="https://arxiv.org/abs/1706.03762",
                id="fetch-input",
            )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    """A yes/no confirmation dialog. Dismisses with ``True``/``False``."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="fetch-dialog"):
            yield Label(self._prompt)
            with Horizontal():
                yield Button("Cancel", variant="default", id="confirm-no")
                yield Button("Delete", variant="error", id="confirm-yes")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)
