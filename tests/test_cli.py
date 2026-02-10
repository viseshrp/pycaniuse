from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from click.testing import CliRunner
from pytest import MonkeyPatch

from caniuse import __version__, cli
from caniuse.exceptions import CaniuseError
from caniuse.model import BrowserSupportBlock, FeatureBasic, FeatureFull, SearchMatch, SupportRange


class _FakeInOut:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty

    def fileno(self) -> int:
        return 0


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_no_matches_exit_nonzero(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(cli, "fetch_search_page", lambda query: "<html></html>")
    monkeypatch.setattr(cli, "parse_search_results", lambda html: [])

    result = runner.invoke(cli.main, ["flexbox"])

    assert result.exit_code != 0
    assert "No matches found" in result.output


def test_exact_slug_shortcut_skips_selector(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(cli, "fetch_search_page", lambda query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda html: [
            SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox"),
            SearchMatch(slug="css-grid", title="CSS Grid", href="/css-grid"),
        ],
    )
    monkeypatch.setattr(cli, "fetch_feature_page", lambda slug: "feature")
    monkeypatch.setattr(
        cli,
        "parse_feature_basic",
        lambda html, slug: FeatureBasic(
            slug=slug,
            title="CSS Flexible Box Layout Module",
            spec_url="https://example.com/spec",
            spec_status="CR",
            usage_supported=95.0,
            usage_partial=1.0,
            usage_total=96.0,
            description_text="desc",
            browser_blocks=[],
            parse_warnings=[],
        ),
    )

    called = {"selector": False}

    def _selector(_matches: list[SearchMatch]) -> None:
        called["selector"] = True
        return None

    monkeypatch.setattr(cli, "select_match", _selector)

    result = runner.invoke(cli.main, ["flexbox"])

    assert result.exit_code == 0
    assert called["selector"] is False
    assert "CSS Flexible Box Layout Module" in result.output


def test_single_result_shortcut_skips_selector(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(cli, "fetch_search_page", lambda query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda html: [SearchMatch(slug="grid", title="Grid", href="/grid")],
    )
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
            parse_warnings=[],
        ),
    )
    monkeypatch.setattr(cli, "select_match", lambda _matches: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(cli, "render_basic", lambda feature_basic: feature_basic.title)

    result = runner.invoke(cli.main, ["css", "grid"])
    assert result.exit_code == 0
    assert "Grid" in result.output


def test_full_mode_warning_prints(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(cli, "fetch_search_page", lambda query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda html: [SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox")],
    )
    monkeypatch.setattr(cli, "fetch_feature_page", lambda slug: "feature")
    monkeypatch.setattr(
        cli,
        "parse_feature_full",
        lambda html, slug: FeatureFull(
            slug=slug,
            title="Flexbox",
            spec_url=None,
            spec_status=None,
            usage_supported=None,
            usage_partial=None,
            usage_total=None,
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
            parse_warnings=["support"],
            notes_text=None,
            resources=[],
            subfeatures=[],
            tabs={},
        ),
    )
    called = {"ran": False}

    def _run_fullscreen(_feature: FeatureFull) -> None:
        called["ran"] = True

    monkeypatch.setattr(cli, "run_fullscreen", _run_fullscreen)

    result = runner.invoke(cli.main, ["flexbox", "--full"])
    assert result.exit_code == 0
    assert "Some sections could not be parsed" in result.output
    assert called["ran"] is True


def test_multiple_matches_tty_path_skips_non_interactive_notice(monkeypatch: MonkeyPatch) -> None:
    @contextmanager
    def _fake_shared_client() -> Iterator[object]:
        yield object()

    class _FakeConsole:
        def __init__(self) -> None:
            self.printed: list[object] = []

        def print(self, obj: object, **_kwargs: object) -> None:
            self.printed.append(obj)

    fake_console = _FakeConsole()

    monkeypatch.setattr(cli, "use_shared_client", _fake_shared_client)
    monkeypatch.setattr(cli, "Console", lambda: fake_console)
    monkeypatch.setattr(cli, "fetch_search_page", lambda query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda html: [
            SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox"),
            SearchMatch(slug="grid", title="Grid", href="/grid"),
        ],
    )
    monkeypatch.setattr(cli.sys, "stdin", _FakeInOut(is_tty=True))
    monkeypatch.setattr(cli.sys, "stdout", _FakeInOut(is_tty=True))
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
            parse_warnings=[],
        ),
    )
    monkeypatch.setattr(cli, "render_basic", lambda feature_basic: feature_basic.title)

    callback = cli.main.callback
    assert callback is not None
    callback(query=("g",), full_mode=False)

    rendered = "\n".join(str(item) for item in fake_console.printed)
    assert "Grid" in rendered
    assert "Multiple matches found in non-interactive mode." not in rendered


def test_cli_wraps_fetches_in_shared_client_context(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()
    state = {
        "entered": 0,
        "exited": 0,
        "active": False,
        "search_in_context": False,
        "feature_in_context": False,
    }

    @contextmanager
    def _fake_shared_client() -> Iterator[object]:
        state["entered"] += 1
        state["active"] = True
        try:
            yield object()
        finally:
            state["active"] = False
            state["exited"] += 1

    def _fetch_search_page(_query: str) -> str:
        state["search_in_context"] = state["active"]
        return "search"

    def _fetch_feature_page(_slug: str) -> str:
        state["feature_in_context"] = state["active"]
        return "feature"

    monkeypatch.setattr(cli, "use_shared_client", _fake_shared_client)
    monkeypatch.setattr(cli, "fetch_search_page", _fetch_search_page)
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda _html: [SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox")],
    )
    monkeypatch.setattr(cli, "fetch_feature_page", _fetch_feature_page)
    monkeypatch.setattr(
        cli,
        "parse_feature_basic",
        lambda _html, slug: FeatureBasic(
            slug=slug,
            title="Flexbox",
            spec_url=None,
            spec_status=None,
            usage_supported=None,
            usage_partial=None,
            usage_total=None,
            description_text="",
            browser_blocks=[],
            parse_warnings=[],
        ),
    )
    monkeypatch.setattr(cli, "render_basic", lambda feature_basic: feature_basic.title)

    result = runner.invoke(cli.main, ["flexbox"])
    assert result.exit_code == 0
    assert state["entered"] == 1
    assert state["exited"] == 1
    assert state["search_in_context"] is True
    assert state["feature_in_context"] is True


def test_cli_error_path_still_exits_shared_client_context(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()
    state = {"entered": 0, "exited": 0}

    @contextmanager
    def _fake_shared_client() -> Iterator[object]:
        state["entered"] += 1
        try:
            yield object()
        finally:
            state["exited"] += 1

    class _BoomError(CaniuseError):
        pass

    monkeypatch.setattr(cli, "use_shared_client", _fake_shared_client)
    monkeypatch.setattr(
        cli,
        "fetch_search_page",
        lambda _query: (_ for _ in ()).throw(_BoomError("boom")),
    )

    result = runner.invoke(cli.main, ["flexbox"])
    assert result.exit_code != 0
    assert "Error: boom" in result.output
    assert state["entered"] == 1
    assert state["exited"] == 1


def test_tui_flag_removed() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["flexbox", "--tui"])
    assert result.exit_code != 0
    assert "No such option: --tui" in result.output


def test_multiple_matches_non_interactive_notice(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(cli, "fetch_search_page", lambda _query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda _html: [
            SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox"),
            SearchMatch(slug="grid", title="Grid", href="/grid"),
        ],
    )
    monkeypatch.setattr(cli, "fetch_feature_page", lambda _slug: "feature")
    monkeypatch.setattr(
        cli,
        "parse_feature_basic",
        lambda _html, slug: FeatureBasic(
            slug=slug,
            title="Grid",
            spec_url=None,
            spec_status=None,
            usage_supported=None,
            usage_partial=None,
            usage_total=None,
            description_text="",
            browser_blocks=[],
            parse_warnings=[],
        ),
    )
    monkeypatch.setattr(cli, "render_basic", lambda feature_basic: feature_basic.title)
    monkeypatch.setattr(cli, "select_match", lambda matches: matches[0].slug)

    result = runner.invoke(cli.main, ["css"])
    assert result.exit_code == 0
    assert "Multiple matches found in non-interactive mode." in result.output


def test_selection_canceled_exits(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(cli, "fetch_search_page", lambda _query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda _html: [
            SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox"),
            SearchMatch(slug="grid", title="Grid", href="/grid"),
        ],
    )
    monkeypatch.setattr(cli, "select_match", lambda _matches: None)

    result = runner.invoke(cli.main, ["css"])
    assert result.exit_code != 0
    assert "Selection canceled." in result.output


def test_basic_mode_warning_prints(monkeypatch: MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(cli, "fetch_search_page", lambda _query: "search")
    monkeypatch.setattr(
        cli,
        "parse_search_results",
        lambda _html: [SearchMatch(slug="flexbox", title="Flexbox", href="/flexbox")],
    )
    monkeypatch.setattr(cli, "fetch_feature_page", lambda _slug: "feature")
    monkeypatch.setattr(
        cli,
        "parse_feature_basic",
        lambda _html, slug: FeatureBasic(
            slug=slug,
            title="Flexbox",
            spec_url=None,
            spec_status=None,
            usage_supported=None,
            usage_partial=None,
            usage_total=None,
            description_text="",
            browser_blocks=[],
            parse_warnings=["usage"],
        ),
    )
    monkeypatch.setattr(cli, "render_basic", lambda feature_basic: feature_basic.title)

    result = runner.invoke(cli.main, ["flexbox"])
    assert result.exit_code == 0
    assert "Some sections could not be parsed" in result.output
