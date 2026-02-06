from __future__ import annotations

from click.testing import CliRunner
from pytest import MonkeyPatch

from caniuse import __version__, cli
from caniuse.model import FeatureBasic, SearchMatch


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
