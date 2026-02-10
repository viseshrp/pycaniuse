from __future__ import annotations

import json
from typing import ClassVar

import pytest
from rich.console import Console

from caniuse.model import BrowserSupportBlock, FeatureBasic, SupportRange
import caniuse.parse_feature as parse_feature_module
from caniuse.parse_feature import _parse_support_range_text, parse_feature_basic, parse_feature_full
import caniuse.parse_search as parse_search_module
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
    assert text_utils.ellipsize("abc", 10) == "abc"
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
    assert _slug_from_href("/bad.slug") is None
    assert _slug_from_href("/bad_slug") == "bad_slug"
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


def test_parse_search_results_prefers_backend_api_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <head><title>"gap" | Can I use</title></head>
      <body><div class='search-results'><a href='/flexbox-gap'>Gap</a></div></body>
    </html>
    """

    monkeypatch.setattr(
        parse_search_module,
        "fetch_search_feature_ids",
        lambda _query: ["mdn-css_properties_gap", "flexbox-gap"],
    )
    monkeypatch.setattr(
        parse_search_module,
        "fetch_support_data",
        lambda **_kwargs: {
            "fullData": [
                {"id": "mdn-css_properties_gap", "title": "CSS property: gap"},
                {"id": "flexbox-gap", "title": "gap property for Flexbox"},
            ]
        },
    )

    matches = parse_search_results(html)

    assert [match.slug for match in matches] == ["mdn-css_properties_gap", "flexbox-gap"]
    assert [match.title for match in matches] == ["CSS property: gap", "gap property for Flexbox"]


def test_parse_search_results_keeps_html_fallback_when_api_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <head><title>"gap" | Can I use</title></head>
      <body>
        <div class='search-results'>
          <a href='/flexbox-gap'>gap property for Flexbox</a>
          <a href='/multicolumn'>CSS3 Multiple column layout</a>
        </div>
      </body>
    </html>
    """

    def _boom(_query: str) -> list[str]:
        raise parse_search_module.CaniuseError("boom")

    monkeypatch.setattr(parse_search_module, "fetch_search_feature_ids", _boom)

    matches = parse_search_results(html)

    assert [match.slug for match in matches] == ["flexbox-gap", "multicolumn"]


def test_parse_search_results_uses_input_query_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html>
      <body>
        <div class='section__search-results'></div>
        <input id='feat_search' value='  gap  ' />
        <div class='search-results'>
          <a href='/flexbox-gap'>gap property for Flexbox</a>
        </div>
      </body>
    </html>
    """
    monkeypatch.setattr(parse_search_module, "fetch_search_feature_ids", lambda _query: [])

    matches = parse_search_results(html)

    assert [match.slug for match in matches] == ["flexbox-gap"]


def test_parse_search_results_ignores_blank_input_query_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <body>
        <div class='section__search-results'></div>
        <input id='feat_search' value='   ' />
        <div class='search-results'>
          <a href='/flexbox-gap'>gap property for Flexbox</a>
        </div>
      </body>
    </html>
    """

    def _boom(_query: str) -> list[str]:
        raise AssertionError

    monkeypatch.setattr(parse_search_module, "fetch_search_feature_ids", _boom)

    matches = parse_search_results(html)
    assert [match.slug for match in matches] == ["flexbox-gap"]


def test_parse_search_results_ignores_missing_input_query_attr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <body>
        <div class='section__search-results'></div>
        <input id='feat_search' />
        <div class='search-results'>
          <a href='/flexbox-gap'>gap property for Flexbox</a>
        </div>
      </body>
    </html>
    """

    def _boom(_query: str) -> list[str]:
        raise AssertionError

    monkeypatch.setattr(parse_search_module, "fetch_search_feature_ids", _boom)

    matches = parse_search_results(html)
    assert [match.slug for match in matches] == ["flexbox-gap"]


def test_parse_search_results_handles_malformed_support_data_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <head><title>"gap" | Can I use</title></head>
      <body><div class='search-results'><a href='/flexbox-gap'>Gap</a></div></body>
    </html>
    """
    monkeypatch.setattr(
        parse_search_module,
        "fetch_search_feature_ids",
        lambda _query: ["bad.id", "flexbox-gap", "mdn-css_properties_gap"],
    )
    monkeypatch.setattr(
        parse_search_module,
        "fetch_support_data",
        lambda **_kwargs: {
            "fullData": [
                "bad-entry",
                {"id": 1, "title": "wrong types"},
                {"id": "flexbox-gap", "title": "gap property for Flexbox"},
            ]
        },
    )

    matches = parse_search_results(html)

    assert [match.slug for match in matches] == ["flexbox-gap", "mdn-css_properties_gap"]
    assert [match.title for match in matches] == [
        "gap property for Flexbox",
        "mdn-css_properties_gap",
    ]


def test_parse_search_results_uses_ids_when_support_payload_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <head><title>"gap" | Can I use</title></head>
      <body><div class='search-results'><a href='/flexbox-gap'>Gap</a></div></body>
    </html>
    """
    monkeypatch.setattr(
        parse_search_module,
        "fetch_search_feature_ids",
        lambda _query: ["flexbox-gap", "mdn-css_properties_gap"],
    )

    def _boom(**_kwargs: object) -> dict[str, object]:
        raise parse_search_module.CaniuseError("boom")

    monkeypatch.setattr(parse_search_module, "fetch_support_data", _boom)

    matches = parse_search_results(html)

    assert [match.slug for match in matches] == ["flexbox-gap", "mdn-css_properties_gap"]
    assert [match.title for match in matches] == ["flexbox-gap", "mdn-css_properties_gap"]


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

    outer_renderables = list(getattr(rendered, "renderables", []))
    assert outer_renderables
    panel = outer_renderables[0]
    body_lines = list(getattr(getattr(panel, "renderable", None), "renderables", []))
    spec_line = body_lines[1]
    link_spans = [span for span in getattr(spec_line, "spans", []) if "link " in str(span.style)]
    assert any("https://www.w3.org/TR/css3-flexbox/" in str(span.style) for span in link_spans)

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


def test_parse_feature_full_uses_initial_data_and_dynamic_tabs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_payload = [
        {
            "id": "flexbox",
            "bug_count": 2,
            "link_count": 1,
            "children": ["flexbox-gap"],
        }
    ]
    encoded_initial = json.dumps(initial_payload).replace("\\", "\\\\").replace('"', '\\"')
    html = f"""
    <html><body>
      <h1 class="feature-title">Flexbox</h1>
      <a class="specification cr" href="/spec">Flexbox - CR</a>
      <li class="support-stats" data-usage-id="region.global">
        <span class="support">95.00%</span>
        <span class="partial">1.00%</span>
        <span class="total">96.00%</span>
      </li>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading browser--chrome">Chrome</h4>
          <ol><li class="stat-cell y current" title="x">1-2</li></ol>
        </div>
      </div>
      <script>window.initialFeatData = {{id: "flexbox", data: "{encoded_initial}"}};</script>
    </body></html>
    """

    def _fake_aux(_slug: str, data_type: str) -> list[dict[str, str]]:
        if data_type == "bugs":
            return [{"description": "Bug one"}, {"description": "Bug two"}]
        if data_type == "links":
            return [{"title": "Specification", "url": "https://example.com/spec"}]
        return []

    monkeypatch.setattr(parse_feature_module, "fetch_feature_aux_data", _fake_aux)

    full = parse_feature_full(html, slug="flexbox")

    assert full.known_issues == ["Bug one", "Bug two"]
    assert full.resources == [("Specification", "https://example.com/spec")]
    assert full.subfeatures == [("flexbox-gap", "https://caniuse.com/flexbox-gap")]
    assert list(full.tabs.keys()) == ["Known issues", "Resources", "Sub-features"]


def test_parse_feature_full_excludes_notes_tab_for_ciu_mdn_wf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parse_feature_module, "fetch_feature_aux_data", lambda *_args: [])

    ciu_payload = [
        {
            "id": "flexbox-gap",
            "notes": "note",
            "notes_by_num": {"1": "a"},
            "children": None,
            "bug_count": 0,
            "link_count": 0,
        }
    ]
    ciu_data = json.dumps(ciu_payload).replace("\\", "\\\\").replace('"', '\\"')
    ciu_html = f"""
    <html><body>
      <h1 class="feature-title">gap property for Flexbox</h1>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading browser--chrome">Chrome</h4>
          <ol><li class="stat-cell y current">1-2</li></ol>
        </div>
      </div>
      <script>window.initialFeatData = {{id: "flexbox-gap", data: "{ciu_data}"}};</script>
    </body></html>
    """
    ciu = parse_feature_full(ciu_html, slug="flexbox-gap")
    assert "Notes" not in ciu.tabs

    mdn_payload = [
        {
            "id": "mdn-css_properties_column-gap",
            "path": "css/properties/column-gap.json",
            "mdn_url": "https://developer.mozilla.org/docs/Web/CSS/Reference/Properties/column-gap",
            "children": [],
        }
    ]
    mdn_data = json.dumps(mdn_payload).replace("\\", "\\\\").replace('"', '\\"')
    mdn_html = f"""
    <html><body>
      <h1 class="feature-title">CSS property: column-gap</h1>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading browser--chrome">Chrome</h4>
          <ol><li class="stat-cell y current">1-2</li></ol>
        </div>
      </div>
      <script>
        window.initialFeatData = {{id: "mdn-css_properties_column-gap", data: "{mdn_data}"}};
      </script>
    </body></html>
    """
    mdn = parse_feature_full(mdn_html, slug="mdn-css_properties_column-gap")
    assert "Notes" not in mdn.tabs

    wf_payload = [
        {
            "id": "wf-font-metric-overrides",
            "bcd_features": ["mdn-api_fontface_linegapoverride"],
            "children": [],
        }
    ]
    wf_data = json.dumps(wf_payload).replace("\\", "\\\\").replace('"', '\\"')
    wf_html = f"""
    <html><body>
      <h1 class="feature-title">Font metric overrides</h1>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading browser--chrome">Chrome</h4>
          <ol><li class="stat-cell y current">1-2</li></ol>
        </div>
      </div>
      <script>
        window.initialFeatData = {{id: "wf-font-metric-overrides", data: "{wf_data}"}};
      </script>
    </body></html>
    """
    wf = parse_feature_full(wf_html, slug="wf-font-metric-overrides")
    assert "Notes" not in wf.tabs


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


def test_parse_feature_initial_payload_and_helpers_edge_cases() -> None:
    assert (
        parse_feature_module._parse_initial_feature_data(
            '<script>window.initialFeatData = {id: "x", data: "not-json"};</script>'
        )
        is None
    )

    assert (
        parse_feature_module._parse_initial_feature_data(
            '<script>window.initialFeatData = {id: "x", data: "[]"};</script>'
        )
        is None
    )

    assert (
        parse_feature_module._parse_initial_feature_data(
            '<script>window.initialFeatData = {id: "x", data: "[1]"};</script>'
        )
        is None
    )

    issues = parse_feature_module._parse_known_issues(
        [{"description": "  one  "}, {"description": ""}, {"description": 1}]
    )
    assert issues == ["one"]

    resources = parse_feature_module._parse_resource_entries(
        [
            {"title": 1, "url": "https://example.com/x"},
            {"title": " ", "url": "https://example.com/x"},
            {"title": "Doc", "url": " "},
            {"title": "Good", "url": "/ok"},
        ]
    )
    assert resources == [("Good", "https://caniuse.com/ok")]

    subfeatures = parse_feature_module._parse_subfeatures_from_initial_data(
        {
            "children": [
                {"id": "Flexbox-Gap", "title": "Gap"},
                {"id": "flexbox-gap", "title": "Gap duplicate"},
                {"title": "Missing id"},
                "mdn-css_properties_gap",
            ]
        }
    )
    assert subfeatures == [
        ("Gap", "https://caniuse.com/flexbox-gap"),
        ("mdn-css_properties_gap", "https://caniuse.com/mdn-css_properties_gap"),
    ]


def test_parse_feature_support_text_raw_fallback_and_api_error_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _NodeWithRawText:
        def to_text(self) -> str:
            return "TP"

    assert _parse_support_range_text(_NodeWithRawText()) == "TP"

    initial_payload = [
        {"id": "flexbox", "bug_count": 1, "link_count": "unknown", "children": ["flexbox-gap"]}
    ]
    encoded_initial = json.dumps(initial_payload).replace("\\", "\\\\").replace('"', '\\"')
    html = f"""
    <html><body>
      <h1 class="feature-title">Flexbox</h1>
      <dl class="single-feat-resources"><dd><a href="/existing">Existing</a></dd></dl>
      <dl><dt>Sub-features:</dt><dd><a href="/dom-sub">DOM sub</a></dd></dl>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading browser--chrome">Chrome</h4>
          <ol><li class="stat-cell y current">1-2</li></ol>
        </div>
      </div>
      <script>window.initialFeatData = {{id: "flexbox", data: "{encoded_initial}"}};</script>
    </body></html>
    """

    calls: list[str] = []

    def _boom_aux(_slug: str, data_type: str) -> list[dict[str, str]]:
        calls.append(data_type)
        raise parse_feature_module.CaniuseError("boom")

    monkeypatch.setattr(parse_feature_module, "fetch_feature_aux_data", _boom_aux)

    full = parse_feature_full(html, slug="flexbox")

    assert calls == ["bugs"]
    assert full.known_issues == []
    assert full.resources == [("Existing", "https://caniuse.com/existing")]
    assert full.subfeatures == [("DOM sub", "https://caniuse.com/dom-sub")]


def test_parse_feature_full_ignores_links_fetch_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    initial_payload = [{"id": "flexbox", "bug_count": 0, "link_count": 1, "children": []}]
    encoded_initial = json.dumps(initial_payload).replace("\\", "\\\\").replace('"', '\\"')
    html = f"""
    <html><body>
      <h1 class="feature-title">Flexbox</h1>
      <div class="support-container">
        <div class="support-list">
          <h4 class="browser-heading browser--chrome">Chrome</h4>
          <ol><li class="stat-cell y current">1-2</li></ol>
        </div>
      </div>
      <script>window.initialFeatData = {{id: "flexbox", data: "{encoded_initial}"}};</script>
    </body></html>
    """

    calls: list[str] = []

    def _boom_aux(_slug: str, data_type: str) -> list[dict[str, str]]:
        calls.append(data_type)
        raise parse_feature_module.CaniuseError("boom")

    monkeypatch.setattr(parse_feature_module, "fetch_feature_aux_data", _boom_aux)

    full = parse_feature_full(html, slug="flexbox")

    assert calls == ["links"]
    assert full.resources == []
