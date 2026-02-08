from __future__ import annotations

import pytest

from caniuse.http import fetch_feature_page
from caniuse.parse_feature import parse_feature_full


@pytest.mark.canary
def test_caniuse_feature_page_html_shape_is_parseable_live() -> None:
    """
    Canary test: fetch a real caniuse.com feature page and ensure our parser still succeeds.

    This is intentionally a single, live-network test to detect upstream HTML layout changes.
    """
    slug = "flexbox"
    html = fetch_feature_page(slug)

    # Quick sanity check to avoid passing on empty/error interstitial HTML.
    assert "<html" in html.lower()

    feature = parse_feature_full(html, slug=slug)

    # If these fail, caniuse page structure likely changed and parser needs updates.
    assert feature.title
    assert feature.spec_url is not None
    assert feature.browser_blocks
    assert any(block.browser_key == "chrome" for block in feature.browser_blocks)
    assert feature.parse_warnings == []

