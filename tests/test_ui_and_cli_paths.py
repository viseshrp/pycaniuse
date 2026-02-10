from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest
from rich.text import Text

from caniuse.model import BrowserSupportBlock, FeatureFull, SearchMatch, SupportRange
from caniuse.ui import fullscreen as fs
from caniuse.ui import select as ui_select


class _FakeInOut:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


class _FakeConsole:
    def __init__(self, *, width: int = 120, height: int = 40) -> None:
        self.size = SimpleNamespace(width=width, height=height)
        self.printed: list[object] = []

    def print(self, obj: object, **_kwargs: object) -> None:
        self.printed.append(obj)


def _sample_feature_full(*, with_tabs: bool = True, browser_count: int = 2) -> FeatureFull:
    blocks = [
        BrowserSupportBlock(
            browser_name=f"Browser-{i}",
            browser_key=f"browser_{i}",
            ranges=[
                SupportRange(
                    range_text="1-2",
                    status="y",
                    is_past=False,
                    is_current=True,
                    is_future=False,
                    title_attr="Global usage: 3.21% - Supported",
                    raw_classes=("#1",),
                ),
                SupportRange(
                    range_text="3",
                    status="a",
                    is_past=True,
                    is_current=False,
                    is_future=False,
                    title_attr="",
                    raw_classes=(),
                ),
            ],
        )
        for i in range(browser_count)
    ]

    return FeatureFull(
        slug="flexbox",
        title="Flexbox",
        spec_url="https://example.com/spec",
        spec_status="CR",
        usage_supported=96.0,
        usage_partial=1.0,
        usage_total=97.0,
        description_text="Method of positioning elements.",
        browser_blocks=blocks,
        parse_warnings=[],
        notes_text="Note text",
        known_issues=["Issue text"],
        resources=[("Res", "https://example.com/res")],
        subfeatures=[("Sub", "https://example.com/sub")],
        baseline_status="high",
        baseline_low_date="2015-09-30",
        baseline_high_date="2018-03-30",
        tabs={"Notes": "notes line", "Resources": "resource line"} if with_tabs else {},
    )


def test_select_match_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
    ]

    assert ui_select.select_match([]) is None
    assert ui_select.select_match([matches[0]]) == "a"

    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(False))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(False))
    assert ui_select.select_match(matches) == "a"

    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(True))
    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole())
    answers = iter(["2"])
    monkeypatch.setattr(ui_select.Prompt, "ask", lambda *_a, **_k: next(answers))
    assert ui_select.select_match(matches) == "b"


def test_select_match_retries_and_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
    ]

    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(True))
    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole())

    prompts = iter(["bad", "q"])
    monkeypatch.setattr(ui_select.Prompt, "ask", lambda *_a, **_k: next(prompts))
    assert ui_select.select_match(matches) is None


def test_select_match_interactive_does_not_import_textual(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
    ]
    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(True))
    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole())
    monkeypatch.setattr(ui_select.Prompt, "ask", lambda *_a, **_k: "1")

    original_import = builtins.__import__

    def _guarded_import(
        name: str,
        globals_: object | None = None,
        locals_: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name.startswith("textual"):
            raise AssertionError
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    assert ui_select.select_match(matches) == "a"


def test_fullscreen_static_and_tty_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()

    fake_console = _FakeConsole()
    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(False))
    fs.run_fullscreen(feature)
    assert fake_console.printed

    called = {"textual": False}

    def _run_textual(arg: FeatureFull) -> None:
        called["textual"] = True
        assert arg is feature

    from caniuse.ui import textual_fullscreen as tui_full

    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(True))
    monkeypatch.setattr(tui_full, "run_textual_fullscreen", _run_textual)
    fs.run_fullscreen(feature)
    assert called["textual"] is True


def test_fullscreen_non_tty_does_not_import_textual(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    monkeypatch.setattr(fs, "Console", lambda: _FakeConsole())
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(False))

    original_import = builtins.__import__

    def _guarded_import(
        name: str,
        globals_: object | None = None,
        locals_: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name.startswith("textual"):
            raise AssertionError
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    fs.run_fullscreen(feature)


def test_fullscreen_render_helpers_cover_core_paths() -> None:
    feature = _sample_feature_full(with_tabs=True)

    assert fs._support_lines(feature)
    lines = fs._feature_lines(feature)
    assert "Browser Support" in lines
    assert fs._render_lines(feature, 50)

    sections = fs._tab_sections(feature)
    assert sections[0][0] == "Notes"
    assert any(name == "Notes" for name, _ in sections)

    no_tabs_sections = fs._tab_sections(_sample_feature_full(with_tabs=False))
    assert any(name == "Resources" for name, _ in no_tabs_sections)


def test_fullscreen_link_and_usage_parsing() -> None:
    assert fs._extract_global_usage("Global usage: 12.34% - Supported") == "12.34%"
    assert fs._extract_global_usage("No usage") is None

    plain = fs._linkify_line("plain text")
    assert isinstance(plain, Text)

    linked = fs._linkify_line("see https://example.com now")
    assert any("link https://example.com" in span.style for span in linked.spans if span.style)

    markdown = fs._linkify_line("visit [Spec](https://example.com/spec)")
    assert any(
        "link https://example.com/spec" in span.style for span in markdown.spans if span.style
    )


def test_fullscreen_state_and_navigation_helpers() -> None:
    feature = _sample_feature_full(browser_count=3)
    state = fs._TuiState()

    fs._normalize_state(state, feature)
    fs._move_browser(state, feature, 1)
    assert state.selected_browser == 1

    fs._scroll_browser_ranges(state, feature, 1)
    assert state.range_scroll == 1

    fs._switch_tab(state, feature, 1)
    assert state.tab_index == 1

    fs._scroll_tab(state, feature, 5)
    assert state.tab_scroll >= 0

    state.browser_visible_count = 2
    fs._page_browsers(state, feature, 1)
    assert state.selected_browser in {1, 2}

    fs._jump_home(state)
    assert state.range_scroll == 0
    assert state.tab_scroll == 0

    fs._jump_end(state, feature)
    assert state.range_scroll >= 0
    assert state.tab_scroll >= 0


def test_fullscreen_layout_builder() -> None:
    feature = _sample_feature_full()
    state = fs._TuiState()

    layout = fs._build_layout_for_size(feature, state, width=120, height=40)
    assert layout["feature"] is not None
    assert layout["support"] is not None
    assert layout["details"] is not None
    assert layout["footer"] is not None


def test_textual_fullscreen_actions_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    from caniuse.ui import textual_fullscreen as tui_full

    feature = _sample_feature_full()
    app = tui_full._FeatureFullApp(feature)

    monkeypatch.setattr(app, "_refresh_frame", lambda: None)

    calls: list[str] = []
    monkeypatch.setattr(tui_full.ui, "_move_browser", lambda *_args: calls.append("move"))
    monkeypatch.setattr(
        tui_full.ui, "_scroll_browser_ranges", lambda *_args: calls.append("scroll")
    )
    monkeypatch.setattr(tui_full.ui, "_page_browsers", lambda *_args: calls.append("page"))
    monkeypatch.setattr(tui_full.ui, "_scroll_tab", lambda *_args: calls.append("tab_scroll"))
    monkeypatch.setattr(tui_full.ui, "_jump_home", lambda *_args: calls.append("home"))
    monkeypatch.setattr(tui_full.ui, "_jump_end", lambda *_args: calls.append("end"))
    monkeypatch.setattr(tui_full.ui, "_switch_tab", lambda *_args: calls.append("switch"))

    app.action_prev_browser()
    app.action_next_browser()
    app.action_scroll_up()
    app.action_scroll_down()
    app.action_page_up()
    app.action_page_down()
    app.action_home()
    app.action_end()
    app.action_next_tab()
    app.action_prev_tab()

    assert "move" in calls
    assert "scroll" in calls
    assert "page" in calls
    assert "tab_scroll" in calls
    assert "home" in calls
    assert "end" in calls
    assert "switch" in calls


def test_textual_fullscreen_quit_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from caniuse.ui import textual_fullscreen as tui_full

    app = tui_full._FeatureFullApp(_sample_feature_full())
    called = {"exit": False}
    monkeypatch.setattr(app, "exit", lambda: called.__setitem__("exit", True))
    app.action_quit_app()
    assert called["exit"] is True
