from __future__ import annotations

from types import SimpleNamespace

from click.testing import CliRunner
import pytest
from rich.text import Text

from caniuse import cli
from caniuse.exceptions import CaniuseError
from caniuse.model import BrowserSupportBlock, FeatureBasic, FeatureFull, SearchMatch, SupportRange
from caniuse.ui import fullscreen as fs
from caniuse.ui import select as ui_select


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


class _FakeConsole:
    def __init__(self, width: int = 120, height: int = 40, inputs: list[str] | None = None) -> None:
        self.size = SimpleNamespace(width=width, height=height)
        self.printed: list[object] = []
        self._inputs = list(inputs or [])
        self.pager_calls: list[str] = []
        self.pager_styles: list[bool] = []

    def print(self, obj: object, **_kwargs: object) -> None:
        self.printed.append(obj)

    def input(self, _prompt: str = "") -> str:
        if self._inputs:
            return self._inputs.pop(0)
        return "q"

    def pager(self, *, styles: bool = False) -> _FakePager:
        self.pager_styles.append(styles)
        return _FakePager(self.pager_calls)


class _FakeConsoleNoPager:
    def __init__(self, width: int = 120, height: int = 40, inputs: list[str] | None = None) -> None:
        self.size = SimpleNamespace(width=width, height=height)
        self.printed: list[object] = []
        self._inputs = list(inputs or [])

    def print(self, obj: object, **_kwargs: object) -> None:
        self.printed.append(obj)

    def input(self, _prompt: str = "") -> str:
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


class _FakeStdinRead:
    def __init__(self, chars: str, is_tty: bool = True) -> None:
        self._chars = list(chars)
        self._is_tty = is_tty

    def read(self, _: int) -> str:
        return self._chars.pop(0)

    def isatty(self) -> bool:
        return self._is_tty

    def fileno(self) -> int:
        return 0


_SelectResult = tuple[list[_FakeStdinRead], list[object], list[object]]


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


def test_raw_mode_enabled_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _RawStdin:
        def fileno(self) -> int:
            return 7

    monkeypatch.setattr(ui_select.sys, "stdin", _RawStdin())
    monkeypatch.setattr(ui_select.termios, "tcgetattr", lambda fd: ["old", fd])
    monkeypatch.setattr(
        ui_select.termios,
        "tcsetattr",
        lambda fd, _mode, _old: calls.append(f"setattr:{fd}"),
    )
    monkeypatch.setattr(ui_select.tty, "setraw", lambda fd: calls.append(f"setraw:{fd}"))
    with ui_select._raw_mode(enabled=True):
        calls.append("inside-select")

    monkeypatch.setattr(fs.sys, "stdin", _RawStdin())
    monkeypatch.setattr(fs.termios, "tcgetattr", lambda fd: ["old", fd])
    monkeypatch.setattr(fs.termios, "tcsetattr", lambda fd, _mode, _old: calls.append(f"fs:{fd}"))
    monkeypatch.setattr(fs.tty, "setraw", lambda fd: calls.append(f"fsraw:{fd}"))
    with fs._raw_mode(enabled=True):
        calls.append("inside-fullscreen")

    assert "inside-select" in calls
    assert "inside-fullscreen" in calls


def test_raw_mode_disabled_paths() -> None:
    with ui_select._raw_mode(enabled=False):
        pass
    with fs._raw_mode(enabled=False):
        pass


def test_select_read_key_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui_select.select, "select", lambda *_args, **_kwargs: ([], [], []))
    assert ui_select._read_key() is None

    stdin = _FakeStdinRead("\n")
    monkeypatch.setattr(ui_select.sys, "stdin", stdin)
    monkeypatch.setattr(ui_select.select, "select", lambda *_args, **_kwargs: ([stdin], [], []))
    assert ui_select._read_key() == "enter"

    stdin = _FakeStdinRead("q")
    monkeypatch.setattr(ui_select.sys, "stdin", stdin)
    monkeypatch.setattr(ui_select.select, "select", lambda *_args, **_kwargs: ([stdin], [], []))
    assert ui_select._read_key() == "q"

    stdin = _FakeStdinRead("\x1b[A")
    monkeypatch.setattr(ui_select.sys, "stdin", stdin)

    calls = {"count": 0}

    def _sel(*_args: object, **_kwargs: object) -> _SelectResult:
        calls["count"] += 1
        return ([stdin], [], [])

    monkeypatch.setattr(ui_select.select, "select", _sel)
    assert ui_select._read_key() == "up"

    stdin = _FakeStdinRead("\x1b")
    monkeypatch.setattr(ui_select.sys, "stdin", stdin)
    monkeypatch.setattr(
        ui_select.select,
        "select",
        lambda *_args, **_kwargs: ([stdin], [], []) if stdin._chars else ([], [], []),
    )
    assert ui_select._read_key() == "esc"

    stdin = _FakeStdinRead("x")
    monkeypatch.setattr(ui_select.sys, "stdin", stdin)
    monkeypatch.setattr(ui_select.select, "select", lambda *_args, **_kwargs: ([stdin], [], []))
    assert ui_select._read_key() is None


def test_select_match_non_tty_and_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        SearchMatch(slug="a", title="A", href="/a"),
        SearchMatch(slug="b", title="B", href="/b"),
    ]

    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=False))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=False))
    assert ui_select.select_match(matches) == "a"

    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole(inputs=["2"]))
    monkeypatch.setattr(ui_select.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(ui_select.sys, "stdout", _FakeInOut(is_tty=True))

    assert ui_select.select_match(matches) == "b"


def test_select_match_cancel_and_single_item(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ui_select.select_match([]) is None
    assert ui_select.select_match([SearchMatch(slug="a", title="A", href="/a")]) == "a"

    monkeypatch.setattr(ui_select, "Console", lambda: _FakeConsole(inputs=["q"]))
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


def test_fullscreen_read_key_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs.select, "select", lambda *_args, **_kwargs: ([], [], []))
    assert fs._read_key() is None

    stdin = _FakeStdinRead("q")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(fs.select, "select", lambda *_args, **_kwargs: ([stdin], [], []))
    assert fs._read_key() == "q"

    stdin = _FakeStdinRead("\x1b[C")
    monkeypatch.setattr(fs.sys, "stdin", stdin)

    def _sel(*_args: object, **_kwargs: object) -> _SelectResult:
        return ([stdin], [], [])

    monkeypatch.setattr(fs.select, "select", _sel)
    assert fs._read_key() == "right"

    stdin = _FakeStdinRead("\x1b[5~")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(fs.select, "select", _sel)
    assert fs._read_key() == "pgup"

    stdin = _FakeStdinRead("7")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(fs.select, "select", lambda *_args, **_kwargs: ([stdin], [], []))
    assert fs._read_key() == "7"

    stdin = _FakeStdinRead("\n")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(fs.select, "select", lambda *_args, **_kwargs: ([stdin], [], []))
    assert fs._read_key() == "enter"

    stdin = _FakeStdinRead("x")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(fs.select, "select", lambda *_args, **_kwargs: ([stdin], [], []))
    assert fs._read_key() is None

    stdin = _FakeStdinRead("\x1b")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(
        fs.select,
        "select",
        lambda *_args, **_kwargs: ([stdin], [], []) if stdin._chars else ([], [], []),
    )
    assert fs._read_key() == "esc"


def test_fullscreen_read_key_escape_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _FakeStdinRead("\x1bX")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(
        fs.select,
        "select",
        lambda *_args, **_kwargs: ([stdin], [], []) if stdin._chars else ([], [], []),
    )
    assert fs._read_key() == "esc"

    stdin = _FakeStdinRead("\x1b[")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(
        fs.select,
        "select",
        lambda *_args, **_kwargs: ([stdin], [], []) if stdin._chars else ([], [], []),
    )
    assert fs._read_key() == "esc"

    stdin = _FakeStdinRead("\x1b[9")
    monkeypatch.setattr(fs.sys, "stdin", stdin)
    monkeypatch.setattr(
        fs.select,
        "select",
        lambda *_args, **_kwargs: ([stdin], [], []) if stdin._chars else ([], [], []),
    )
    assert fs._read_key() is None


def test_fullscreen_support_lines_and_non_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    assert fs._support_lines(feature)

    fake_console = _FakeConsole()
    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=False))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=False))

    fs.run_fullscreen(feature)
    assert fake_console.printed


def test_fullscreen_tty_uses_pager(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _sample_feature_full()
    fake_console = _FakeConsole(width=40, height=10)
    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=True))

    fs.run_fullscreen(feature)
    assert fake_console.pager_calls == ["enter", "exit"]
    assert fake_console.pager_styles == [True]
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

    fake_console = _FakeConsole()
    monkeypatch.setattr(fs, "Console", lambda: fake_console)
    monkeypatch.setattr(fs.sys, "stdin", _FakeInOut(is_tty=False))
    monkeypatch.setattr(fs.sys, "stdout", _FakeInOut(is_tty=False))

    fs.run_fullscreen(feature)

    panel_payloads = []
    for obj in fake_console.printed:
        renderable = getattr(obj, "renderable", None)
        if isinstance(renderable, Text):
            panel_payloads.append(renderable.plain)
    assert any("[older version](https://example.com/old)" in payload for payload in panel_payloads)


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

    def _run_fullscreen(_feature: FeatureFull) -> None:
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
