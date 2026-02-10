"""Textual app for interactive full-screen feature rendering."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from ..model import FeatureFull
from . import fullscreen as ui


class _FeatureFullApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #frame {
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("left", "prev_browser", show=False),
        Binding("right", "next_browser", show=False),
        Binding("up", "scroll_up", show=False),
        Binding("down", "scroll_down", show=False),
        Binding("pageup", "page_up", show=False),
        Binding("pagedown", "page_down", show=False),
        Binding("home", "home", show=False),
        Binding("end", "end", show=False),
        Binding("tab,ctrl+i", "next_tab", show=False, priority=True),
        Binding("shift+tab,backtab", "prev_tab", show=False, priority=True),
        Binding("left_square_bracket", "prev_tab", show=False),
        Binding("right_square_bracket", "next_tab", show=False),
        Binding("q", "quit_app", show=False),
        Binding("escape", "quit_app", show=False),
    ]

    def __init__(self, feature: FeatureFull) -> None:
        super().__init__()
        self._feature = feature
        self._state = ui._TuiState()

    def compose(self) -> ComposeResult:
        yield Static(id="frame")

    def on_mount(self) -> None:
        self._refresh_frame()

    def on_resize(self) -> None:
        self._refresh_frame()

    def _refresh_frame(self) -> None:
        frame = self.query_one("#frame", Static)
        frame.update(
            ui._build_layout_for_size(
                self._feature,
                self._state,
                max(self.size.width, 40),
                max(self.size.height, 12),
            )
        )

    def action_prev_browser(self) -> None:
        ui._move_browser(self._state, self._feature, -1)
        self._refresh_frame()

    def action_next_browser(self) -> None:
        ui._move_browser(self._state, self._feature, 1)
        self._refresh_frame()

    def action_scroll_up(self) -> None:
        ui._scroll_browser_ranges(self._state, self._feature, -1)
        self._refresh_frame()

    def action_scroll_down(self) -> None:
        ui._scroll_browser_ranges(self._state, self._feature, 1)
        self._refresh_frame()

    def action_page_up(self) -> None:
        ui._page_browsers(self._state, self._feature, -1)
        ui._scroll_tab(self._state, self._feature, -5)
        self._refresh_frame()

    def action_page_down(self) -> None:
        ui._page_browsers(self._state, self._feature, 1)
        ui._scroll_tab(self._state, self._feature, 5)
        self._refresh_frame()

    def action_home(self) -> None:
        ui._jump_home(self._state)
        self._refresh_frame()

    def action_end(self) -> None:
        ui._jump_end(self._state, self._feature)
        self._refresh_frame()

    def action_next_tab(self) -> None:
        ui._switch_tab(self._state, self._feature, 1)
        self._refresh_frame()

    def action_prev_tab(self) -> None:
        ui._switch_tab(self._state, self._feature, -1)
        self._refresh_frame()

    def action_quit_app(self) -> None:
        self.exit()


def run_textual_fullscreen(feature: FeatureFull) -> None:
    """Run the Textual app for full-screen feature display."""
    _FeatureFullApp(feature).run()
