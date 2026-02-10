"""Textual app for selecting one feature from search matches."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from ..model import SearchMatch


class _SelectMatchApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
        align: center middle;
    }

    #container {
        width: 92;
        max-height: 90%;
        border: round #5f87ff;
        padding: 1 1;
        background: $surface;
    }

    #title {
        margin-bottom: 1;
        text-style: bold;
    }

    #options {
        height: 1fr;
        border: round #808080;
    }

    #hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "confirm", show=False),
        Binding("q", "cancel", show=False),
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, matches: list[SearchMatch]) -> None:
        super().__init__()
        self._matches = matches
        self.selection: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("Select a feature", id="title")
        yield OptionList(
            *[
                Option(f"[bold]{match.title}[/bold] [dim]/{match.slug}[/dim]", id=match.slug)
                for match in self._matches
            ],
            id="options",
        )
        yield Static("Use ↑/↓ to move, Enter to select, q/Esc to cancel.", id="hint")

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.selection = self._matches[event.option_index].slug
        self.exit()

    def action_confirm(self) -> None:
        options = self.query_one(OptionList)
        if options.highlighted is None:
            return
        self.selection = self._matches[options.highlighted].slug
        self.exit()

    def action_cancel(self) -> None:
        self.selection = None
        self.exit()


def run_textual_select(matches: list[SearchMatch]) -> str | None:
    """Run Textual selector and return selected slug."""
    app = _SelectMatchApp(matches)
    app.run()
    return app.selection
