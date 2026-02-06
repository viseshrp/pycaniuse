from __future__ import annotations

from caniuse.parse_feature import parse_feature_basic, parse_feature_full
from caniuse.parse_search import parse_search_results


SEARCH_HTML = """
<html>
  <body>
    <a href="/">Home</a>
    <a href="/flexbox">CSS Flexible Box Layout Module</a>
    <a href="/css-grid">CSS Grid Layout</a>
    <a href="https://caniuse.com/css-grid-lanes">External banner</a>
    <a href="/issue-list">Issue list</a>
  </body>
</html>
"""

FEATURE_HTML = """
<html>
  <head><title>CSS Flexible Box Layout Module | Can I use</title></head>
  <body>
    <h1 class="feature-title">CSS Flexible Box Layout Module</h1>
    <a href="https://www.w3.org/TR/css3-flexbox/" class="specification cr" title="W3C Candidate Recommendation">
      CSS Flexible Box Layout Module - CR
    </a>
    <li class="support-stats" data-usage-id="region.global">
      <span class="support">96.39%</span>
      <span class="partial">0.4%</span>
      <span class="total">96.79%</span>
    </li>
    <div class="feature-description"><p>Method of positioning items with <code>flex</code>.</p></div>

    <div class="support-container">
      <div class="support-list">
        <h4 class="browser-heading browser--chrome">Chrome</h4>
        <ol>
          <li class="stat-cell a x #1 past" title="Global usage: partial">4 - 20</li>
          <li class="stat-cell y current" title="Global usage: supported">21 - 999</li>
        </ol>
      </div>
      <div class="support-list">
        <h4 class="browser-heading browser--edge">Edge</h4>
        <ol>
          <li class="stat-cell y current" title="Global usage: supported">12 - 999</li>
        </ol>
      </div>
      <div class="support-list">
        <h4 class="browser-heading browser--firefox">Firefox</h4>
        <ol>
          <li class="stat-cell y current" title="Global usage: supported">28 - 999</li>
        </ol>
      </div>
      <div class="support-list">
        <h4 class="browser-heading browser--safari">Safari</h4>
        <ol>
          <li class="stat-cell y current" title="Global usage: supported">9 - 999</li>
        </ol>
      </div>
      <div class="support-list">
        <h4 class="browser-heading browser--opera">Opera</h4>
        <ol>
          <li class="stat-cell y current" title="Global usage: supported">12 - 999</li>
        </ol>
      </div>
      <div class="support-list">
        <h4 class="browser-heading browser--kaios">KaiOS Browser</h4>
        <ol>
          <li class="stat-cell n current" title="Global usage: no">2.5</li>
        </ol>
      </div>
    </div>

    <div class="single-page__notes">
      <p>Most partial support refers to an <a href="https://example.com/old">older version</a>.</p>
    </div>

    <dl class="single-feat-resources">
      <dt>Resources:</dt>
      <dd><a href="https://example.com/r1">Resource One</a></dd>
      <dd><a href="/r2">Resource Two</a></dd>
    </dl>

    <dl>
      <dt>Sub-features:</dt>
      <dd><a href="./flexbox-gap">gap property for Flexbox</a></dd>
      <dt>Other:</dt>
      <dd>Ignored</dd>
    </dl>
  </body>
</html>
"""


def test_parse_search_results_fallback_strategy() -> None:
    matches = parse_search_results(SEARCH_HTML)
    assert [match.slug for match in matches] == ["flexbox", "css-grid"]


def test_parse_feature_basic_fields_and_browser_filter() -> None:
    parsed = parse_feature_basic(FEATURE_HTML, slug="flexbox")

    assert parsed.title == "CSS Flexible Box Layout Module"
    assert parsed.spec_url == "https://www.w3.org/TR/css3-flexbox/"
    assert parsed.spec_status == "CR"
    assert parsed.usage_supported == 96.39
    assert parsed.usage_partial == 0.4
    assert parsed.usage_total == 96.79
    assert "`flex`" in parsed.description_text

    browser_keys = [block.browser_key for block in parsed.browser_blocks]
    assert browser_keys == ["chrome", "edge", "firefox", "safari", "opera"]

    chrome = parsed.browser_blocks[0]
    assert chrome.ranges[0].status == "a"
    assert chrome.ranges[0].range_text == "4 - 20"
    assert "#1" in chrome.ranges[0].raw_classes


def test_parse_feature_full_includes_tabs_and_all_browsers() -> None:
    parsed = parse_feature_full(FEATURE_HTML, slug="flexbox")

    assert [block.browser_key for block in parsed.browser_blocks][-1] == "kaios"
    assert list(parsed.tabs.keys()) == ["Notes", "Resources", "Sub-features"]
    assert parsed.notes_text is not None
    assert len(parsed.resources) == 2
    assert parsed.subfeatures == [
        ("gap property for Flexbox", "https://caniuse.com/flexbox-gap"),
    ]
