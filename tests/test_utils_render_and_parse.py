from __future__ import annotations

from typing import ClassVar

import pytest
from rich.console import Console

from caniuse.model import BrowserSupportBlock, FeatureBasic, SupportRange
from caniuse.parse_feature import _parse_support_range_text, parse_feature_basic, parse_feature_full
from caniuse.parse_search import _slug_from_href, parse_search_results
from caniuse.render_basic import _usage_line, render_basic
from caniuse.util import html as html_utils
from caniuse.util import text as text_utils


def test_text_utils_branches() -> None:
    assert text_utils.normalize_whitespace(" a\n  b ") == "a b"
    assert text_utils.parse_percent(None) is None
    assert text_utils.parse_percent("96,79%") == 96.79
    assert text_utils.parse_percent("oops") is None
    assert text_utils.wrap_lines("alpha\n\nbeta", 5)
    assert text_utils.ellipsize("abc", 0) == ""
    assert text_utils.ellipsize("abc", 1) == "…"
    assert text_utils.ellipsize("abcdef", 4) == "abc…"
    assert text_utils.extract_note_markers(("#1", "x", "#4")) == ["1", "4"]


def test_html_utils_with_document_and_invalid_node(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = html_utils.parse_document("<html><body><div class='x'>hi</div></body></html>")
    assert html_utils.first(doc, ".x") is not None
    assert len(html_utils.all_nodes(doc, "div")) == 1

    class _BadQuery:
        def query(self, selector: str) -> list[object]:
            _ = selector
            raise RuntimeError("bad")

    assert html_utils.all_nodes(_BadQuery(), "div") == []
    assert html_utils.text(None) == ""
    assert html_utils.markdown_text(None) == ""
    assert html_utils.attr(None, "href") is None
    assert html_utils.class_tokens(None) == ()
    assert html_utils.safe_join_url("https://caniuse.com", None) is None

    class _DataNode:
        data = "  hello   world "

    assert html_utils.text(_DataNode()) == "hello world"

    class _AttrNode:
        attrs: ClassVar[dict[str, str]] = {"href": "/x", "class": "a b"}

    assert html_utils.attr(_AttrNode(), "href") == "/x"
    assert html_utils.class_tokens(_AttrNode()) == ("a", "b")

    monkeypatch.setenv("PYCANIUSE_DEBUG", "1")
    assert html_utils.debug_enabled() is True
    html_utils.debug_log("selector matched")


def test_html_utils_text_markdown_fallbacks() -> None:
    class _Raises:
        def to_text(self) -> str:
            raise ValueError("bad")

    class _RaisesMd:
        def to_markdown(self) -> str:
            raise ValueError("bad")

        def to_text(self) -> str:
            return " text "

    class _NoAttrs:
        attrs = 1

    assert html_utils.text(_Raises()) == ""
    assert html_utils.markdown_text(_RaisesMd()) == "text"
    assert html_utils.attr(_NoAttrs(), "x") is None


def test_html_utils_additional_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    class _NoQuery:
        pass

    class _EmptyNode:
        pass

    class _NoMarkdown:
        def to_text(self) -> str:
            return " plain "

    assert html_utils.all_nodes(_NoQuery(), ".x") == []
    assert html_utils.text(_EmptyNode()) == ""
    assert html_utils.markdown_text(_NoMarkdown()) == "plain"

    monkeypatch.setenv("PYCANIUSE_DEBUG", "0")
    html_utils.debug_log("not logged")


def test_parse_search_slug_and_primary_strategy() -> None:
    assert _slug_from_href(None) is None
    assert _slug_from_href("https://caniuse.com/flexbox") is None
    assert _slug_from_href("/flexbox?x=1") is None
    assert _slug_from_href("flexbox") is None
    assert _slug_from_href("/issue-list") is None
    assert _slug_from_href("/bad_slug") is None
    assert _slug_from_href("/flexbox") == "flexbox"

    html = """
    <html><body>
      <div class='search-results'>
        <a href='/grid'>CSS Grid</a>
        <a href='/grid'>CSS Grid Duplicate</a>
      </div>
      <a href='/fallback'>fallback</a>
    </body></html>
    """
    matches = parse_search_results(html)
    assert [m.slug for m in matches] == ["grid"]


def test_render_basic_and_usage_branches() -> None:
    feature = FeatureBasic(
        slug="flexbox",
        title="Flexbox",
        spec_url="https://www.w3.org/TR/css3-flexbox/",
        spec_status="CR",
        usage_supported=90.1,
        usage_partial=2.2,
        usage_total=92.3,
        description_text="desc",
        browser_blocks=[
            BrowserSupportBlock(
                browser_name="Chrome",
                browser_key="chrome",
                ranges=[
                    SupportRange(
                        range_text="1-2",
                        status="a",
                        is_past=True,
                        is_current=False,
                        is_future=False,
                        title_attr="x",
                        raw_classes=("#1",),
                    )
                ],
            )
        ],
        parse_warnings=[],
    )

    rendered = render_basic(feature)
    console = Console(record=True, width=120)
    console.print(rendered)
    output = console.export_text()

    assert "Flexbox" in output
    assert "Spec:" in output
    assert "Usage:" in output
    assert "See notes: 1" in output

    none_usage = FeatureBasic(
        slug="x",
        title="x",
        spec_url=None,
        spec_status=None,
        usage_supported=None,
        usage_partial=None,
        usage_total=None,
        description_text="",
        browser_blocks=[],
        parse_warnings=[],
    )
    assert _usage_line(none_usage) is None


def test_parse_feature_fallbacks_and_missing_sections() -> None:
    minimal = """
    <html>
      <head><title>Fallback Title | Can I use</title></head>
      <body>
        <a class="specification wd" href="/spec">Specification only</a>
        <div class="support-container">
          <div class="support-list">
            <h4 class="browser-heading">Custom Browser</h4>
            <ol>
              <li class="stat-cell current" title="unknown"></li>
              <li class="stat-cell current" title="unknown">TP</li>
            </ol>
          </div>
        </div>
      </body>
    </html>
    """
    basic = parse_feature_basic(minimal, slug="fallback-slug")
    assert basic.title == "Fallback Title"
    assert basic.spec_url == "https://caniuse.com/spec"
    assert basic.spec_status == "WD"
    assert basic.description_text == ""
    assert basic.usage_total is None
    assert basic.parse_warnings == ["support"]

    full = parse_feature_full(minimal, slug="fallback-slug")
    assert full.browser_blocks[0].browser_key == "custom-browser"
    assert full.browser_blocks[0].ranges[0].status == "u"
    assert full.notes_text is None
    assert full.resources == []
    assert full.subfeatures == []
    assert full.tabs == {}


def test_parse_feature_section_edge_cases() -> None:
    html = """
    <html><body>
      <h1 class="feature-title">X</h1>
      <div class="single-page__notes"></div>
      <dl class="single-feat-resources">
        <dd><a href="">Bad</a></dd>
        <dd><a href="/ok">Okay</a></dd>
      </dl>
      <dl>
        <dt>Sub-features:</dt>
        <dd>No links here</dd>
        <dt>Other:</dt>
        <dd><a href="/other">Other link</a></dd>
      </dl>
    </body></html>
    """
    full = parse_feature_full(html, slug="x")
    assert full.notes_text is None
    assert full.resources == [("Okay", "https://caniuse.com/ok")]
    assert full.subfeatures == []
    assert list(full.tabs.keys()) == ["Resources"]


def test_parse_feature_support_range_text_ignores_a11y_status_suffix() -> None:
    html = """
    <html><body>
      <h1 class="feature-title">Flexbox</h1>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading browser--chrome">Chrome</h4>
          <ol>
            <li class="stat-cell a current">
              <span class="forced-colors-only">◐</span>
              4 - 20
              <span class="a11y-only">: Partial support</span>
            </li>
          </ol>
        </div>
      </div>
    </body></html>
    """
    basic = parse_feature_basic(html, slug="flexbox")
    assert basic.browser_blocks
    assert basic.browser_blocks[0].ranges[0].range_text == "4 - 20"


def test_parse_feature_slug_title_fallback_and_invalid_browser_heading() -> None:
    html = """
    <html><body>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading"></h4>
          <ol><li class="stat-cell y current">1</li></ol>
        </div>
      </div>
    </body></html>
    """
    full = parse_feature_full(html, slug="fallback-slug")
    assert full.title == "fallback-slug"
    assert full.browser_blocks == []
    assert full.parse_warnings == ["support"]


def test_parse_support_range_text_colon_fallback_and_subfeature_filtering() -> None:
    class _NodeWithToText:
        def to_text(self) -> str:
            return "prefix 9 : Partial support"

    assert _parse_support_range_text(_NodeWithToText()) == "9"

    html = """
    <html><body>
      <h1 class="feature-title">Feature</h1>
      <dl>
        <dt>Sub-features:</dt>
        <dd>
          <a href="">Bad</a>
          <a href="/good">Good</a>
        </dd>
      </dl>
    </body></html>
    """
    full = parse_feature_full(html, slug="feature")
    assert full.subfeatures == [("Good", "https://caniuse.com/good")]
