from __future__ import annotations

from collections.abc import Iterator
import io
from types import ModuleType, SimpleNamespace
from typing import Literal, cast

from click.testing import CliRunner
import pytest
from rich.console import Console
from rich.text import Text

from caniuse import cli
from caniuse.exceptions import CaniuseError
from caniuse.model import BrowserSupportBlock, FeatureBasic, FeatureFull, SearchMatch, SupportRange
from caniuse.ui import fullscreen as fs
from caniuse.ui import select as ui_select
from caniuse.ui.textual_fullscreen import _FeatureFullApp


class _FakePager:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def __enter__(self) -> _FakePager:
        self._calls.append("enter")
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object | None,
    ) -> None:
        self._calls.append("exit")
        return None


class _FakeScreen:
    def __enter__(self) -> _FakeScreen:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object | None,
    ) -> None:
        return None


class _FakeConsole:
    def __init__(self, width: int = 120, height: int = 40, inputs: list[str] | None = None) -> None:
        self.size = SimpleNamespace(width=width, height=height)
        self.printed: list[object] = []
        self._inputs = list(inputs or [])
        self.pager_calls: list[str] = []
        self.pager_styles: list[bool] = []

    def print(self, obj: object, **_kwargs: object) -> None:
        self.printed.append(obj)

    def input(
        self,
        _prompt: str = "",
        *,
        password: bool = False,
        stream: object | None = None,
    ) -> str:
        _ = password
        _ = stream
        if self._inputs:
            return self._inputs.pop(0)
        return "q"

    def pager(self, *, styles: bool = False) -> _FakePager:
        self.pager_styles.append(styles)
        return _FakePager(self.pager_calls)

    def screen(self, *, hide_cursor: bool = False) -> _FakeScreen:
        _ = hide_cursor
        return _FakeScreen()


class _FakeConsoleNoPager:
    def __init__(self, width: int = 120, height: int = 40, inputs: list[str] | None = None) -> None:
        self.size = SimpleNamespace(width=width, height=height)
        self.printed: list[object] = []
        self._inputs = list(inputs or [])

    def print(self, obj: object, **_kwargs: object) -> None:
        self.printed.append(obj)

    def input(
        self,
        _prompt: str = "",
        *,
        password: bool = False,
        stream: object | None = None,
    ) -> str:
        _ = password
        _ = stream
        if self._inputs:
            return self._inputs.pop(0)
        return "q"


class _FakeInOut:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty

    def fileno(self) -> int:
        return 0


def _sample_feature_full() -> FeatureFull:
    return FeatureFull(
        slug="flexbox",
        title="Flexbox",
        spec_url="https://example.com/spec",
        spec_status="CR",
        usage_supported=1.0,
        usage_partial=2.0,
        usage_total=3.0,
        description_text="desc",
        browser_blocks=[
            BrowserSupportBlock(
                browser_name="Chrome",
                browser_key="chrome",
                ranges=[
                    SupportRange(
                        range_text="1-2",
                        status="y",
                        is_past=False,
                        is_current=True,
                        is_future=False,
                        title_attr="",
                        raw_classes=(),
                    )
                ],
            )
        ],
        parse_warnings=[],
        notes_text="note",
        resources=[("Res", "https://example.com")],
        subfeatures=[("Sub", "https://example.com/sub")],
        tabs={"Notes": "line1", "Resources": "line2", "Sub-features": "line3"},
    )


def _sample_support_range(
    *,
    title_attr: str = "",
    raw_classes: tuple[str, ...] = (),
    status: Literal["y", "n", "a", "u"] = "y",
    is_past: bool = False,
    is_current: bool = True,
    is_future: bool = False,
) -> SupportRange:
    return SupportRange(
        range_text="1-2",
        status=status,
        is_past=is_past,
        is_current=is_current,
        is_future=is_future,
        title_attr=title_attr,
        raw_classes=raw_classes,
    )


def test_select_match_non_tty_and_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
    ]

    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=False))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=False))
    assert ui_select.select_match(matches) == "a"

    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole(inputs=["2"]))
    monkeypatch.setattr(ui_select, "_supports_key_loop", lambda _console: False)
    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=True))

    assert ui_select.select_match(matches) == "b"


def test_select_match_cancel_and_single_item(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ui_select.select_match([]) is None
    assert ui_select.select_match([SearchMatch(slug="a", title="A", href="/a")]) == "a"

    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole(inputs=["q"]))
    monkeypatch.setattr(ui_select, "_supports_key_loop", lambda _console: False)
    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=True))

    assert (
        ui_select.select_match(
            [
                SearchMatch(slug="a", title="A", href="/a"),
                SearchMatch(slug="b", title="B", href="/b"),
            ]
        )
        is None
    )


def test_select_match_invalid_then_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
    ]
    fake_console = _FakeConsole(inputs=["bad", "3", "2"])
    monkeypatch.setattr(ui_select, "Console", lambda: fake_console)
    monkeypatch.setattr(ui_select, "_supports_key_loop", lambda _console: False)
    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=True))

    assert ui_select.select_match(matches) == "b"
    assert "Invalid selection. Try again." in fake_console.printed


def test_select_build_frame() -> None:
    panel = ui_select._build_frame(
        [
            SearchMatch(slug="a", title="A very long title that should ellipsize", href="/a"),
            SearchMatch(slug="b", title="B", href="/b"),
        ],
        selected_idx=1,
        width=20,
        start=0,
        stop=2,
    )
    assert panel.title == "Select a feature"
    group = panel.renderable
    renderables = list(getattr(group, "renderables", []))
    footer = renderables[-1]
    assert isinstance(footer, Text)
    assert "move" in footer.plain
    assert "Enter select" in footer.plain


def test_select_match_interactive_key_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
        SearchMatch(slug="c", title="C", href="/c"),
    ]
    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select, "_supports_key_loop", lambda _console: True)

    class _FakeLive:
        def __init__(self) -> None:
            self.frames: list[object] = []

        def __enter__(self) -> _FakeLive:
            return self

        def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc: BaseException | None,
            _tb: object | None,
        ) -> None:
            return None

        def update(self, frame: object, *, refresh: bool = False) -> None:
            _ = refresh
            self.frames.append(frame)

    fake_console = _FakeConsole(width=120, height=40)
    monkeypatch.setattr(ui_select, "Console", lambda: fake_console)

    keys = iter(["down", "down", "up", "enter"])

    class _FakeRawInput:
        def __enter__(self) -> _FakeRawInput:
            return self

        def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc: BaseException | None,
            _tb: object | None,
        ) -> None:
            return None

        def read_key(self) -> str:
            return next(keys)

    monkeypatch.setattr(ui_select, "_RawInput", _FakeRawInput)

    def _fake_live_factory(*_args: object, **_kwargs: object) -> _FakeLive:
        return _FakeLive()

    monkeypatch.setattr(ui_select, "Live", _fake_live_factory)

    assert ui_select.select_match(matches) == "b"


def test_fullscreen_support_lines_and_non_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    assert fs._support_lines(feature)

    fake_console = _FakeConsole()
    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=False))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=False))

    fs.run_fullscreen(feature)
    assert fake_console.printed


def test_fullscreen_tty_uses_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    fake_console = _FakeConsole(width=40, height=10)
    called = {"tui": False}

    def _run_tui(console: object, arg_feature: FeatureFull) -> None:
        called["tui"] = True
        assert console is fake_console
        assert arg_feature is feature

    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    monkeypatch.setattr(fs, "_supports_tui", lambda _console: True)
    monkeypatch.setattr(fs, "_run_tui", _run_tui)

    fs.run_fullscreen(feature)
    assert called["tui"] is True


def test_fullscreen_textual_force_uses_textual_when_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = _sample_feature_full()
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=True))
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=True))
    called = {"textual": False}

    def _run_textual(arg_feature: FeatureFull) -> bool:
        called["textual"] = True
        assert arg_feature is feature
        return True

    monkeypatch.setattr(fs, "_try_run_textual_tui", _run_textual)
    monkeypatch.setattr(fs, "Console", lambda: _FakeConsole(width=120, height=40))

    fs.run_fullscreen(feature, textual_mode="force")
    assert called["textual"] is True


def test_textual_app_class_loads_and_binds() -> None:
    app = _FeatureFullApp(_sample_feature_full())
    assert app is not None
    assert app.BINDINGS


def test_fullscreen_textual_auto_flag_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=True))
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=True))

    called = {"textual": False, "rich": False}

    def _run_textual(_feature: FeatureFull) -> bool:
        called["textual"] = True
        return False

    def _run_tui(_console: object, _feature: FeatureFull) -> None:
        called["rich"] = True

    monkeypatch.setattr(fs, "_try_run_textual_tui", _run_textual)
    monkeypatch.setattr(fs, "_supports_tui", lambda _console: True)
    monkeypatch.setattr(fs, "_run_tui", _run_tui)
    monkeypatch.setattr(fs, "Console", lambda: _FakeConsole(width=120, height=40))
    monkeypatch.setattr(fs, "_textual_feature_enabled", lambda: True)

    fs.run_fullscreen(feature, textual_mode="auto")
    assert called["textual"] is True
    assert called["rich"] is True

    called = {"textual": False, "rich": False}
    monkeypatch.setattr(fs, "_textual_feature_enabled", lambda: False)
    fs.run_fullscreen(feature, textual_mode="auto")
    assert called["textual"] is False
    assert called["rich"] is True


def test_fullscreen_textual_never_runs_without_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=False))
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=False))
    called = {"textual": False}

    def _run_textual(_feature: FeatureFull) -> bool:
        called["textual"] = True
        return True

    fake_console = _FakeConsole(width=120, height=40)
    monkeypatch.setattr(fs, "_try_run_textual_tui", _run_textual)
    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    fs.run_fullscreen(feature, textual_mode="force")
    assert called["textual"] is False
    assert fake_console.printed


def test_fullscreen_tty_without_pager_falls_back_to_print(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    fake_console = _FakeConsoleNoPager(width=120, height=40)
    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=True))

    fs.run_fullscreen(feature)
    assert fake_console.printed


def test_fullscreen_no_tabs_uses_info_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    feature = FeatureFull(
        slug=feature.slug,
        title=feature.title,
        spec_url=feature.spec_url,
        spec_status=feature.spec_status,
        usage_supported=feature.usage_supported,
        usage_partial=feature.usage_partial,
        usage_total=feature.usage_total,
        description_text=feature.description_text,
        browser_blocks=feature.browser_blocks,
        parse_warnings=feature.parse_warnings,
        notes_text=None,
        resources=[],
        subfeatures=[],
        tabs={},
    )

    monkeypatch.setattr(fs, "Console", lambda: _FakeConsole(width=120, height=40))
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=True))

    fs.run_fullscreen(feature)


def test_fullscreen_non_tty_preserves_literal_brackets(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    feature = FeatureFull(
        slug=feature.slug,
        title=feature.title,
        spec_url=feature.spec_url,
        spec_status=feature.spec_status,
        usage_supported=feature.usage_supported,
        usage_partial=feature.usage_partial,
        usage_total=feature.usage_total,
        description_text=feature.description_text,
        browser_blocks=feature.browser_blocks,
        parse_warnings=feature.parse_warnings,
        notes_text="[older version](https://example.com/old)",
        resources=[],
        subfeatures=[],
        tabs={"Notes": "[older version](https://example.com/old)"},
    )

    console = Console(width=120, height=40, file=io.StringIO(), record=True)
    monkeypatch.setattr(fs, "Console", lambda: console)
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=False))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=False))

    fs.run_fullscreen(feature)

    rendered = console.export_text()
    assert "[older version](https://example.com/old)" in rendered


def test_fullscreen_linkify_produces_clickable_spans() -> None:
    linked = fs._linkify_line(
        "Docs: [older version](https://example.com/old) and https://example.com/new"
    )
    link_styles = [str(span.style) for span in linked.spans if "link " in str(span.style)]
    assert any("https://example.com/old" in style for style in link_styles)
    assert any("https://example.com/new" in style for style in link_styles)

    heading = fs._feature_heading_panel(_sample_feature_full(), width=80)
    heading_lines = list(getattr(heading.renderable, "renderables", []))
    spec_line = heading_lines[1]
    heading_link_styles = [
        str(span.style) for span in spec_line.spans if "link " in str(span.style)
    ]
    assert any("https://example.com/spec" in style for style in heading_link_styles)

    feature = _sample_feature_full()
    feature = FeatureFull(
        slug=feature.slug,
        title=feature.title,
        spec_url=feature.spec_url,
        spec_status=feature.spec_status,
        usage_supported=feature.usage_supported,
        usage_partial=feature.usage_partial,
        usage_total=feature.usage_total,
        description_text=feature.description_text,
        browser_blocks=feature.browser_blocks,
        parse_warnings=feature.parse_warnings,
        notes_text=feature.notes_text,
        resources=feature.resources,
        subfeatures=feature.subfeatures,
        tabs={"Notes": "[old](https://example.com/old)\nhttps://example.com/new"},
    )
    state = fs._TuiState(tab_index=1)
    tab_panel = fs._tab_panel(feature, state, max_rows=10)
    payload_lines = list(getattr(tab_panel.renderable, "renderables", []))
    payload_link_styles = [
        str(span.style)
        for line in payload_lines
        for span in getattr(line, "spans", [])
        if "link " in str(span.style)
    ]
    assert any("https://example.com/old" in style for style in payload_link_styles)
    assert any("https://example.com/new" in style for style in payload_link_styles)


def test_fullscreen_tab_sections_prefer_parsed_tabs_order() -> None:
    feature = _sample_feature_full()
    sections = fs._tab_sections(feature)

    names = [name for name, _ in sections]
    assert names == ["Info", "Notes", "Resources", "Sub-features", "Legend"]
    assert sections[1][1] == ["line1"]
    assert sections[2][1] == ["line2"]
    assert sections[3][1] == ["line3"]


def test_fullscreen_tab_sections_fallback_when_tabs_absent() -> None:
    feature = _sample_feature_full()
    feature = FeatureFull(
        slug=feature.slug,
        title=feature.title,
        spec_url=feature.spec_url,
        spec_status=feature.spec_status,
        usage_supported=feature.usage_supported,
        usage_partial=feature.usage_partial,
        usage_total=feature.usage_total,
        description_text=feature.description_text,
        browser_blocks=feature.browser_blocks,
        parse_warnings=feature.parse_warnings,
        notes_text="notes fallback",
        resources=[("Res", "https://example.com")],
        subfeatures=[("Sub", "https://example.com/sub")],
        tabs={},
    )

    names = [name for name, _ in fs._tab_sections(feature)]
    assert names == ["Info", "Notes", "Resources", "Sub-features", "Legend"]


def test_fullscreen_support_line_includes_era_usage_and_notes() -> None:
    support_range = _sample_support_range(
        title_attr="Global usage: 12.34% - Partial support",
        raw_classes=("#3",),
        status="a",
        is_past=False,
        is_current=False,
        is_future=True,
    )

    line_with_usage = fs._format_support_line(support_range, include_usage=True).plain
    assert "[future]" in line_with_usage
    assert "Partial support" in line_with_usage
    assert "usage:12.34%" in line_with_usage
    assert "notes:3" in line_with_usage

    line_without_usage = fs._format_support_line(support_range, include_usage=False).plain
    assert "usage:12.34%" not in line_without_usage


def test_fullscreen_layout_has_expected_sections_without_removed_header() -> None:
    feature = _sample_feature_full()
    state = fs._TuiState()
    console = Console(width=120, height=40, file=io.StringIO(), record=True)

    layout = fs._build_layout(feature, state, console)
    root_names = [child.name for child in layout.children]
    assert root_names == ["feature", "support", "details", "footer"]
    assert layout["details"].children == []

    console.print(layout)
    rendered = console.export_text()
    assert "Home   News   Compare browsers   About" not in rendered
    assert "January 2026 - New feature announcements available on caniuse.com" not in rendered
    assert "Can I use Flexbox ?   Settings" not in rendered
    assert "Flexbox" in rendered


def test_fullscreen_extract_global_usage_parses_only_expected_pattern() -> None:
    assert fs._extract_global_usage("Global usage: 1.58% - Supported") == "1.58%"
    assert fs._extract_global_usage("usage missing label") is None


def test_cli_full_mode_and_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(cli, "fetch_search_page", lambda query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda html: [SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox")],
    )
    monkeypatch.setattr(cli, "fetch_feature_page", lambda slug: "feature")
    monkeypatch.setattr(cli, "parse_feature_full", lambda html, slug: _sample_feature_full())

    called = {"full": False}

    def _run_fullscreen(_feature: FeatureFull, *, textual_mode: str = "off") -> None:
        _ = textual_mode
        called["full"] = True

    monkeypatch.setattr(cli, "run_fullscreen", _run_fullscreen)

    result = runner.invoke(cli.main, ["flexbox", "--full"])
    assert result.exit_code == 0
    assert called["full"] is True

    class _BoomError(CaniuseError):
        pass

    monkeypatch.setattr(
        cli,
        "fetch_search_page",
        lambda query: (_ for _ in ()).throw(_BoomError("x")),
    )
    result = runner.invoke(cli.main, ["flexbox"])
    assert result.exit_code != 0
    assert "Error" in result.output


def test_cli_multiple_results_cancel_and_basic_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(cli, "fetch_search_page", lambda query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda html: [
            SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox"),
            SearchMatch(slug="grid", title="Grid", href="/grid"),
        ],
    )
    monkeypatch.setattr(cli, "select_match", lambda matches: None)
    result = runner.invoke(cli.main, ["f"])
    assert result.exit_code != 0
    assert "Multiple matches found in non-interactive mode." in result.output
    assert "Selection canceled." in result.output

    monkeypatch.setattr(cli, "select_match", lambda matches: "grid")
    monkeypatch.setattr(cli, "fetch_feature_page", lambda slug: "feature")
    monkeypatch.setattr(
        cli,
        "parse_feature_basic",
        lambda html, slug: FeatureBasic(
            slug=slug,
            title="Grid",
            spec_url=None,
            spec_status=None,
            usage_supported=None,
            usage_partial=None,
            usage_total=None,
            description_text="",
            browser_blocks=[],
            parse_warnings=["support"],
        ),
    )
    monkeypatch.setattr(cli, "render_basic", lambda feature_basic: "basic-output")
    result = runner.invoke(cli.main, ["f"])
    assert result.exit_code == 0
    assert "Some sections could not be parsed" in result.output


def test_select_low_level_key_and_window_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ui_select._visible_window(selected_idx=2, total=3, height=20) == (0, 3)
    assert ui_select._visible_window(selected_idx=9, total=20, height=10) == (7, 11)
    assert ui_select._decode_escape_sequence(b"[A") == "up"
    assert ui_select._decode_escape_sequence(b"[B") == "down"
    assert ui_select._decode_escape_sequence(b"[C") == "noop"
    assert ui_select._decode_escape_sequence(b"OA") == "up"
    assert ui_select._decode_escape_sequence(b"OB") == "down"

    monkeypatch.setattr(ui_select.os, "read", lambda _fd, _n: b"")
    assert ui_select._read_key_posix(0) == "noop"

    monkeypatch.setattr(ui_select.os, "read", lambda _fd, _n: b"q")
    assert ui_select._read_key_posix(0) == "quit"

    monkeypatch.setattr(ui_select.os, "read", lambda _fd, _n: b"\n")
    assert ui_select._read_key_posix(0) == "enter"

    monkeypatch.setattr(ui_select.os, "read", lambda _fd, _n: b"k")
    assert ui_select._read_key_posix(0) == "up"

    monkeypatch.setattr(ui_select.os, "read", lambda _fd, _n: b"j")
    assert ui_select._read_key_posix(0) == "down"

    chunks_up = iter([b"\x1b", b"[", b"A"])
    monkeypatch.setattr(ui_select.os, "read", lambda _fd, _n: next(chunks_up))
    monkeypatch.setattr(ui_select.select, "select", lambda *_args, **_kwargs: ([0], [], []))
    assert ui_select._read_key_posix(0) == "up"

    chunks_unknown = iter([b"\x1b", b"[", b"C"])
    ready: Iterator[tuple[list[int], list[int], list[int]]] = iter(
        [([0], [], []), ([0], [], []), ([], [], [])]
    )
    monkeypatch.setattr(ui_select.os, "read", lambda _fd, _n: next(chunks_unknown))
    monkeypatch.setattr(ui_select.select, "select", lambda *_args, **_kwargs: next(ready))
    assert ui_select._read_key_posix(0) == "noop"


def test_select_windows_raw_input_and_support_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_mod_no_getwch = ModuleType("msvcrt")
    monkeypatch.setitem(ui_select.sys.modules, "msvcrt", fake_mod_no_getwch)
    assert ui_select._read_key_windows() == "noop"

    def _set_windows_chars(chars: list[str]) -> None:
        fake_mod = ModuleType("msvcrt")
        data = list(chars)
        fake_mod.getwch = lambda: data.pop(0)  # type: ignore[attr-defined]
        monkeypatch.setitem(ui_select.sys.modules, "msvcrt", fake_mod)

    _set_windows_chars(["q"])
    assert ui_select._read_key_windows() == "quit"
    _set_windows_chars(["\r"])
    assert ui_select._read_key_windows() == "enter"
    _set_windows_chars(["k"])
    assert ui_select._read_key_windows() == "up"
    _set_windows_chars(["j"])
    assert ui_select._read_key_windows() == "down"
    _set_windows_chars(["\xe0", "H"])
    assert ui_select._read_key_windows() == "up"
    _set_windows_chars(["\xe0", "P"])
    assert ui_select._read_key_windows() == "down"
    _set_windows_chars(["\xe0", "X"])
    assert ui_select._read_key_windows() == "noop"
    _set_windows_chars(["x"])
    assert ui_select._read_key_windows() == "noop"

    monkeypatch.setattr(ui_select.os, "name", "nt", raising=False)
    raw = ui_select._RawInput()
    with raw:
        monkeypatch.setattr(ui_select, "_read_key_windows", lambda: "up")
        assert raw.read_key() == "up"

    calls: dict[str, int] = {"setcbreak": 0, "tcsetattr": 0}
    tty_mod = ModuleType("tty")
    tty_mod.setcbreak = lambda _fd: calls.__setitem__("setcbreak", calls["setcbreak"] + 1)  # type: ignore[attr-defined]
    termios_mod = ModuleType("termios")
    termios_mod.TCSADRAIN = 1  # type: ignore[attr-defined]
    termios_mod.tcgetattr = lambda _fd: "old"  # type: ignore[attr-defined]
    termios_mod.tcsetattr = lambda _fd, _when, _old: calls.__setitem__(  # type: ignore[attr-defined]
        "tcsetattr", calls["tcsetattr"] + 1
    )
    monkeypatch.setitem(ui_select.sys.modules, "tty", tty_mod)
    monkeypatch.setitem(ui_select.sys.modules, "termios", termios_mod)
    monkeypatch.setattr(ui_select.os, "name", "posix", raising=False)
    monkeypatch.setattr(ui_select.sys, "stdin", SimpleNamespace(fileno=lambda: 7, read=lambda: ""))

    raw = ui_select._RawInput()
    raw.__enter__()
    monkeypatch.setattr(ui_select, "_read_key_posix", lambda _fd: "down")
    assert raw.read_key() == "down"
    raw.__exit__(None, None, None)
    assert calls["setcbreak"] == 1
    assert calls["tcsetattr"] == 1

    raw = ui_select._RawInput()
    assert raw.read_key() == "noop"
    raw.__exit__(None, None, None)

    good_inout = SimpleNamespace(
        isatty=lambda: True,
        fileno=lambda: 0,
        read=lambda: "",
    )
    monkeypatch.setattr(ui_select.sys, "stdin", good_inout)
    monkeypatch.setattr(ui_select.sys, "stdout", good_inout)
    assert ui_select._supports_key_loop(cast(Console, _FakeConsole())) is True

    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=False))
    assert ui_select._supports_key_loop(cast(Console, _FakeConsole())) is False

    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=True))
    assert ui_select._supports_key_loop(cast(Console, object())) is False

    monkeypatch.setattr(
        ui_select.sys,
        "stdin",
        SimpleNamespace(isatty=lambda: True, fileno=lambda: 0),
    )
    assert ui_select._supports_key_loop(cast(Console, _FakeConsole())) is False

    monkeypatch.setattr(
        ui_select.sys,
        "stdin",
        SimpleNamespace(
            isatty=lambda: True,
            read=lambda: "",
            fileno=lambda: (_ for _ in ()).throw(ValueError("x")),
        ),
    )
    assert ui_select._supports_key_loop(cast(Console, _FakeConsole())) is False


def test_select_match_interactive_quit_path(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
    ]
    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select, "_supports_key_loop", lambda _console: True)
    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole())

    class _FakeRawInput:
        def __enter__(self) -> _FakeRawInput:
            return self

        def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc: BaseException | None,
            _tb: object | None,
        ) -> None:
            return None

        def read_key(self) -> str:
            return "quit"

    class _FakeLive:
        def __enter__(self) -> _FakeLive:
            return self

        def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc: BaseException | None,
            _tb: object | None,
        ) -> None:
            return None

        def update(self, _frame: object, *, refresh: bool = False) -> None:
            _ = refresh

    monkeypatch.setattr(ui_select, "_RawInput", _FakeRawInput)
    monkeypatch.setattr(ui_select, "Live", lambda *_args, **_kwargs: _FakeLive())
    assert ui_select.select_match(matches) is None


def test_fullscreen_low_level_key_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert fs._decode_escape_sequence(b"[A") == "up"
    assert fs._decode_escape_sequence(b"[B") == "down"
    assert fs._decode_escape_sequence(b"[C") == "right"
    assert fs._decode_escape_sequence(b"[D") == "left"
    assert fs._decode_escape_sequence(b"[5~") == "pageup"
    assert fs._decode_escape_sequence(b"[6~") == "pagedown"
    assert fs._decode_escape_sequence(b"[H") == "home"
    assert fs._decode_escape_sequence(b"[F") == "end"
    assert fs._decode_escape_sequence(b"[Z") == "shift_tab"
    assert fs._decode_escape_sequence(b"[X") == "noop"
    assert fs._decode_escape_sequence(b"OC") == "right"
    assert fs._decode_escape_sequence(b"[5;5~") == "pageup"
    assert fs._decode_escape_sequence(b"[6;2~") == "pagedown"

    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"")
    assert fs._read_key_posix(0) == "noop"

    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"q")
    assert fs._read_key_posix(0) == "quit"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"\t")
    assert fs._read_key_posix(0) == "tab"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"\n")
    assert fs._read_key_posix(0) == "noop"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"[")
    assert fs._read_key_posix(0) == "prev_tab"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"]")
    assert fs._read_key_posix(0) == "next_tab"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"h")
    assert fs._read_key_posix(0) == "left"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"j")
    assert fs._read_key_posix(0) == "down"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"k")
    assert fs._read_key_posix(0) == "up"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"l")
    assert fs._read_key_posix(0) == "right"
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: b"x")
    assert fs._read_key_posix(0) == "noop"

    chunks_up = iter([b"\x1b", b"[", b"A"])
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: next(chunks_up))
    monkeypatch.setattr(fs.select, "select", lambda *_args, **_kwargs: ([0], [], []))
    assert fs._read_key_posix(0) == "up"

    chunks_unknown = iter([b"\x1b", b"[", b"X"])
    ready: Iterator[tuple[list[int], list[int], list[int]]] = iter(
        [([0], [], []), ([0], [], []), ([], [], [])]
    )
    monkeypatch.setattr(fs.os, "read", lambda _fd, _n: next(chunks_unknown))
    monkeypatch.setattr(fs.select, "select", lambda *_args, **_kwargs: next(ready))
    assert fs._read_key_posix(0) == "noop"


def test_fullscreen_windows_raw_input_and_support_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_mod_no_getwch = ModuleType("msvcrt")
    monkeypatch.setitem(fs.sys.modules, "msvcrt", fake_mod_no_getwch)
    assert fs._read_key_windows() == "noop"

    def _set_windows_chars(chars: list[str]) -> None:
        fake_mod = ModuleType("msvcrt")
        data = list(chars)
        fake_mod.getwch = lambda: data.pop(0)  # type: ignore[attr-defined]
        monkeypatch.setitem(fs.sys.modules, "msvcrt", fake_mod)

    _set_windows_chars(["q"])
    assert fs._read_key_windows() == "quit"
    _set_windows_chars(["\t"])
    assert fs._read_key_windows() == "tab"
    _set_windows_chars(["["])
    assert fs._read_key_windows() == "prev_tab"
    _set_windows_chars(["]"])
    assert fs._read_key_windows() == "next_tab"
    _set_windows_chars(["h"])
    assert fs._read_key_windows() == "left"
    _set_windows_chars(["j"])
    assert fs._read_key_windows() == "down"
    _set_windows_chars(["k"])
    assert fs._read_key_windows() == "up"
    _set_windows_chars(["l"])
    assert fs._read_key_windows() == "right"
    _set_windows_chars(["\xe0", "I"])
    assert fs._read_key_windows() == "pageup"
    _set_windows_chars(["\xe0", "Q"])
    assert fs._read_key_windows() == "pagedown"
    _set_windows_chars(["\xe0", "G"])
    assert fs._read_key_windows() == "home"
    _set_windows_chars(["\xe0", "O"])
    assert fs._read_key_windows() == "end"
    _set_windows_chars(["\xe0", "X"])
    assert fs._read_key_windows() == "noop"
    _set_windows_chars(["x"])
    assert fs._read_key_windows() == "noop"

    monkeypatch.setattr(fs.os, "name", "nt", raising=False)
    raw = fs._RawInput()
    with raw:
        monkeypatch.setattr(fs, "_read_key_windows", lambda: "left")
        assert raw.read_key() == "left"

    calls: dict[str, int] = {"setcbreak": 0, "tcsetattr": 0}
    tty_mod = ModuleType("tty")
    tty_mod.setcbreak = lambda _fd: calls.__setitem__("setcbreak", calls["setcbreak"] + 1)  # type: ignore[attr-defined]
    termios_mod = ModuleType("termios")
    termios_mod.TCSADRAIN = 1  # type: ignore[attr-defined]
    termios_mod.tcgetattr = lambda _fd: "old"  # type: ignore[attr-defined]
    termios_mod.tcsetattr = lambda _fd, _when, _old: calls.__setitem__(  # type: ignore[attr-defined]
        "tcsetattr", calls["tcsetattr"] + 1
    )
    monkeypatch.setitem(fs.sys.modules, "tty", tty_mod)
    monkeypatch.setitem(fs.sys.modules, "termios", termios_mod)
    monkeypatch.setattr(fs.os, "name", "posix", raising=False)
    monkeypatch.setattr(fs.sys, "stdin", SimpleNamespace(fileno=lambda: 9, read=lambda: ""))

    raw = fs._RawInput()
    raw.__enter__()
    monkeypatch.setattr(fs, "_read_key_posix", lambda _fd: "right")
    assert raw.read_key() == "right"
    raw.__exit__(None, None, None)
    assert calls["setcbreak"] == 1
    assert calls["tcsetattr"] == 1

    raw = fs._RawInput()
    assert raw.read_key() == "noop"
    raw.__exit__(None, None, None)

    good_inout = SimpleNamespace(
        isatty=lambda: True,
        fileno=lambda: 0,
        read=lambda: "",
    )
    monkeypatch.setattr(fs.sys, "stdin", good_inout)
    monkeypatch.setattr(fs.sys, "stdout", good_inout)
    assert fs._supports_tui(cast(Console, _FakeConsole())) is True

    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=False))
    assert fs._supports_tui(cast(Console, _FakeConsole())) is False

    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=True))
    assert fs._supports_tui(cast(Console, object())) is False

    monkeypatch.setattr(
        fs.sys,
        "stdin",
        SimpleNamespace(isatty=lambda: True, fileno=lambda: 0),
    )
    assert fs._supports_tui(cast(Console, _FakeConsole())) is False

    monkeypatch.setattr(
        fs.sys,
        "stdin",
        SimpleNamespace(
            isatty=lambda: True,
            read=lambda: "",
            fileno=lambda: (_ for _ in ()).throw(ValueError("x")),
        ),
    )
    assert fs._supports_tui(cast(Console, _FakeConsole())) is False


def test_fullscreen_apply_key_panels_and_tui_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    ranges = [
        SupportRange(
            range_text=f"{idx}",
            status="y",
            is_past=True,
            is_current=False,
            is_future=False,
            title_attr="Global usage: 1.00%",
            raw_classes=("#1",),
        )
        for idx in range(1, 8)
    ]
    feature = FeatureFull(
        slug="feat",
        title="Feature",
        spec_url=None,
        spec_status=None,
        usage_supported=None,
        usage_partial=None,
        usage_total=None,
        description_text="",
        browser_blocks=[
            BrowserSupportBlock(browser_name="A", browser_key="a", ranges=ranges),
            BrowserSupportBlock(browser_name="B", browser_key="b", ranges=ranges[:2]),
        ],
        parse_warnings=[],
        notes_text=None,
        resources=[],
        subfeatures=[],
        tabs={"Notes": "\n".join([f"line {idx}" for idx in range(12)])},
    )
    state = fs._TuiState(selected_browser=0, range_scroll=2, tab_index=0, tab_scroll=6)
    assert fs._apply_key("quit", state, feature) is False

    state = fs._TuiState(selected_browser=1, range_scroll=3, tab_index=0, tab_scroll=2)
    assert fs._apply_key("left", state, feature) is True
    assert state.selected_browser == 0
    assert state.range_scroll == 0

    assert fs._apply_key("right", state, feature) is True
    assert state.selected_browser == 1
    assert state.range_scroll == 0

    state.range_scroll = 1
    fs._apply_key("up", state, feature)
    assert state.range_scroll == 0
    fs._apply_key("down", state, feature)
    assert state.range_scroll == 1

    state.tab_index = 0
    state.tab_scroll = 4
    fs._apply_key("tab", state, feature)
    assert state.tab_index == 1
    assert state.tab_scroll == 0
    fs._apply_key("next_tab", state, feature)
    assert state.tab_index == 2
    fs._apply_key("shift_tab", state, feature)
    assert state.tab_index == 1
    fs._apply_key("prev_tab", state, feature)
    assert state.tab_index == 0

    state.tab_index = 1
    state.tab_scroll = 8
    fs._apply_key("pageup", state, feature)
    assert state.selected_browser == 0
    assert state.tab_scroll == 3
    fs._apply_key("pagedown", state, feature)
    assert state.selected_browser == 1
    assert state.tab_scroll == 8

    state.range_scroll = 3
    state.tab_scroll = 5
    fs._apply_key("home", state, feature)
    assert state.range_scroll == 0
    assert state.tab_scroll == 0
    fs._apply_key("end", state, feature)
    assert state.range_scroll == 1
    assert state.tab_scroll > 0

    state = fs._TuiState(selected_browser=0, browser_visible_count=3, tab_index=1, tab_scroll=0)
    fs._apply_key("pagedown", state, feature)
    assert state.selected_browser == 1
    fs._apply_key("pageup", state, feature)
    assert state.selected_browser == 0

    empty = FeatureFull(
        slug="empty",
        title="Empty",
        spec_url=None,
        spec_status=None,
        usage_supported=None,
        usage_partial=None,
        usage_total=None,
        description_text="",
        browser_blocks=[],
        parse_warnings=[],
        notes_text=None,
        resources=[],
        subfeatures=[],
        tabs={},
    )
    state = fs._TuiState(selected_browser=2, range_scroll=5, tab_index=0, tab_scroll=0)
    assert fs._apply_key("left", state, empty) is True
    assert state.selected_browser == 2
    assert fs._era_label(_sample_support_range(is_current=False, is_future=False)) == "past"
    assert fs._tab_sections(empty)[0][1] == ["No additional feature metadata."]

    no_browser_text = Console(record=True, width=100, file=io.StringIO())
    no_browser_text.print(fs._support_overview_panel(empty, fs._TuiState(), width=40, max_rows=6))
    no_browser_text.print(fs._support_detail_panel(empty, fs._TuiState(), max_rows=6))
    rendered_empty = no_browser_text.export_text()
    assert "No browser support blocks found." in rendered_empty
    assert "No browser selected." in rendered_empty

    empty_ranges_feature = FeatureFull(
        slug="empty-ranges",
        title="Empty ranges",
        spec_url=None,
        spec_status=None,
        usage_supported=None,
        usage_partial=None,
        usage_total=None,
        description_text="",
        browser_blocks=[BrowserSupportBlock(browser_name="A", browser_key="a", ranges=[])],
        parse_warnings=[],
        notes_text=None,
        resources=[],
        subfeatures=[],
        tabs={},
    )
    empty_ranges_text = Console(record=True, width=100, file=io.StringIO())
    empty_ranges_text.print(
        fs._support_overview_panel(empty_ranges_feature, fs._TuiState(), width=24, max_rows=6)
    )
    empty_ranges_text.print(
        fs._support_detail_panel(empty_ranges_feature, fs._TuiState(), max_rows=6)
    )
    rendered_empty_ranges = empty_ranges_text.export_text()
    assert "No range data" in rendered_empty_ranges
    assert "No support ranges." in rendered_empty_ranges

    full_text = Console(record=True, width=100, file=io.StringIO())
    full_text.print(fs._support_overview_panel(feature, fs._TuiState(), width=24, max_rows=5))
    full_text.print(fs._feature_heading_panel(feature, width=60))
    rendered_full = full_text.export_text()
    assert "more" in rendered_full
    assert "Unavailable" in rendered_full
    assert "No description available." in rendered_full

    snapshots: list[int] = []

    def _fake_build_layout(
        _feature: FeatureFull,
        state_arg: fs._TuiState,
        _console: object,
    ) -> Text:
        snapshots.append(state_arg.selected_browser)
        return Text("layout")

    class _FakeRawInput:
        def __enter__(self) -> _FakeRawInput:
            self._keys = iter(["right", "quit"])
            return self

        def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc: BaseException | None,
            _tb: object | None,
        ) -> None:
            return None

        def read_key(self) -> str:
            return next(self._keys)

    class _FakeLive:
        def __enter__(self) -> _FakeLive:
            return self

        def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc: BaseException | None,
            _tb: object | None,
        ) -> None:
            return None

        def update(self, _layout: object, *, refresh: bool = False) -> None:
            _ = refresh

    monkeypatch.setattr(fs, "_build_layout", _fake_build_layout)
    monkeypatch.setattr(fs, "_RawInput", _FakeRawInput)
    monkeypatch.setattr(fs, "Live", lambda *_args, **_kwargs: _FakeLive())
    fs._run_tui(cast(Console, _FakeConsole(width=80, height=24)), feature)
    assert 1 in snapshots
