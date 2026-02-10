"""Textual implementation for full-screen feature rendering."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from ..model import FeatureFull
from . import fullscreen as legacy


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
        Binding("left", "left", show=False),
        Binding("right", "right", show=False),
        Binding("up", "up", show=False),
        Binding("down", "down", show=False),
        Binding("pageup", "pageup", show=False),
        Binding("pagedown", "pagedown", show=False),
        Binding("home", "home", show=False),
        Binding("end", "end", show=False),
        Binding("tab", "next_tab", show=False),
        Binding("shift+tab", "prev_tab", show=False),
        Binding("left_square_bracket", "prev_tab", show=False),
        Binding("right_square_bracket", "next_tab", show=False),
        Binding("q", "quit_app", show=False),
        Binding("escape", "quit_app", show=False),
    ]

    def __init__(self, feature: FeatureFull) -> None:
        super().__init__()
        self._feature = feature
        self._state = legacy._TuiState()

    def compose(self) -> ComposeResult:
        yield Static(id="frame")

    def on_mount(self) -> None:
        self._refresh_frame()

    def on_resize(self) -> None:
        self._refresh_frame()

    def _refresh_frame(self) -> None:
        frame = self.query_one("#frame", Static)
        frame.update(
            legacy._build_layout_for_size(
                self._feature,
                self._state,
                max(self.size.width, 40),
                max(self.size.height, 12),
            )
        )

    def _apply(self, key: legacy._KEY) -> None:
        if not legacy._apply_key(key, self._state, self._feature):
            self.exit()
            return
        self._refresh_frame()

    def action_left(self) -> None:
        self._apply("left")

    def action_right(self) -> None:
        self._apply("right")

    def action_up(self) -> None:
        self._apply("up")

    def action_down(self) -> None:
        self._apply("down")

    def action_pageup(self) -> None:
        self._apply("pageup")

    def action_pagedown(self) -> None:
        self._apply("pagedown")

    def action_home(self) -> None:
        self._apply("home")

    def action_end(self) -> None:
        self._apply("end")

    def action_next_tab(self) -> None:
        self._apply("next_tab")

    def action_prev_tab(self) -> None:
        self._apply("prev_tab")

    def action_quit_app(self) -> None:
        self.exit()


def run_textual_fullscreen(feature: FeatureFull) -> None:
    """Run the Textual app for full-screen feature display."""
    _FeatureFullApp(feature).run()
