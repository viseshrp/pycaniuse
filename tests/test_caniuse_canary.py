from __future__ import annotations

import pytest

from caniuse.http import fetch_feature_page, fetch_search_page
from caniuse.parse_feature import parse_feature_basic, parse_feature_full
from caniuse.parse_search import parse_search_results
from caniuse.util.html import all_nodes, attr, class_tokens, first, parse_document, text
from caniuse.util.text import parse_percent


@pytest.mark.canary
def test_caniuse_feature_page_html_shape_is_parseable_live() -> None:
    """
    Canary test: fetch real caniuse.com pages and verify every parser dependency is still present.

    This is intentionally a single, live-network test to detect upstream HTML layout changes.
    """
    query = "flexbox"
    slug = "flexbox"

    search_html = fetch_search_page(query)
    assert "<html" in search_html.lower()

    search_doc = parse_document(search_html)
    primary_search_selectors = (
        ".search-results a[href]",
        ".search-result a[href]",
        ".feature-list a[href]",
        ".features-list a[href]",
        "main a[href]",
    )
    primary_anchor_counts = [
        len(all_nodes(search_doc, selector)) for selector in primary_search_selectors
    ]
    assert any(primary_anchor_counts), "No primary search selector returned any anchors."
    assert all_nodes(search_doc, "a[href]"), "Fallback search selector returned no anchors."

    search_matches = parse_search_results(search_html)
    assert search_matches, "Search parser returned no matches."
    assert any(match.slug == slug for match in search_matches), (
        "Expected slug was not returned by search."
    )

    feature_html = fetch_feature_page(slug)
    assert "<html" in feature_html.lower()
    doc = parse_document(feature_html)

    # Title selectors used by parser.
    title_node = first(doc, ".feature-title")
    assert title_node is not None
    assert text(title_node)
    assert first(doc, "title") is not None

    # Spec selector and fields.
    spec_node = first(doc, "a.specification")
    assert spec_node is not None
    assert attr(spec_node, "href")
    assert text(spec_node)
    assert any(
        class_name != "specification" and class_name.isalpha() and len(class_name) <= 4
        for class_name in class_tokens(spec_node)
    ), "Spec anchor no longer exposes a short status class token."

    # Usage selectors and percentage parsing.
    usage_node = first(doc, 'li.support-stats[data-usage-id="region.global"]')
    assert usage_node is not None
    supported_node = first(usage_node, ".support")
    partial_node = first(usage_node, ".partial")
    total_node = first(usage_node, ".total")
    assert supported_node is not None
    assert partial_node is not None
    assert total_node is not None
    assert parse_percent(text(supported_node)) is not None
    assert parse_percent(text(partial_node)) is not None
    assert parse_percent(text(total_node)) is not None

    # Description selector.
    description_node = first(doc, ".feature-description")
    assert description_node is not None
    assert text(description_node)

    # Browser support selectors and cell fields.
    support_nodes = all_nodes(doc, ".support-container .support-list")
    assert support_nodes
    all_stat_cells: list[object] = []
    saw_browser_key_class = False
    for support_node in support_nodes:
        heading = first(support_node, "h4.browser-heading")
        assert heading is not None
        assert text(heading)
        if any(token.startswith("browser--") for token in class_tokens(heading)):
            saw_browser_key_class = True
        all_stat_cells.extend(all_nodes(support_node, "ol > li.stat-cell"))
    assert saw_browser_key_class
    assert all_stat_cells
    assert any(
        any(status_class in {"y", "n", "a", "u"} for status_class in class_tokens(stat_cell))
        for stat_cell in all_stat_cells
    ), "No support status class token found in any stat cell."
    assert any(attr(stat_cell, "title") for stat_cell in all_stat_cells), (
        "No stat cell had a title attribute."
    )
    assert any(text(stat_cell) for stat_cell in all_stat_cells), "No stat cell contained text."
    assert any(
        any(
            getattr(child, "name", None) == "#text" and text(child)
            for child in list(getattr(stat_cell, "children", []))
        )
        for stat_cell in all_stat_cells
    ), "No stat cell contained direct #text child content for range parsing."

    # Full-mode optional sections our parser reads.
    resources_nodes = all_nodes(doc, "dl.single-feat-resources dd a")
    assert resources_nodes
    assert any(attr(node, "href") and text(node) for node in resources_nodes)
    assert any(
        text(dt_node).rstrip(":").strip().lower() == "sub-features"
        for dt_node in all_nodes(doc, "dl dt")
    )

    # Parser-level contracts.
    full_feature = parse_feature_full(feature_html, slug=slug)
    assert full_feature.parse_warnings == []
    assert full_feature.title
    assert full_feature.spec_url is not None
    assert full_feature.browser_blocks
    assert full_feature.resources
    assert full_feature.subfeatures
    assert {"Resources", "Sub-features"}.issubset(full_feature.tabs.keys())

    basic_feature = parse_feature_basic(feature_html, slug=slug)
    assert basic_feature.parse_warnings == []
    basic_browser_keys = {block.browser_key for block in basic_feature.browser_blocks}
    for key in ("chrome", "edge", "firefox", "safari", "opera"):
        assert key in basic_browser_keys
