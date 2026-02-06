"""Search result parser for caniuse search pages."""

from __future__ import annotations

import re

from .model import SearchMatch
from .util.html import all_nodes, attr, parse_document, text

_SLUG_RE = re.compile(r"^[a-z0-9-]+$")
_IGNORED_PREFIXES = (
    "/ciu/",
    "/issue-list",
    "/about",
    "/news",
    "/compare",
    "/usage-table",
    "/stats",
    "/support/",
)


def _slug_from_href(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return None
    if "?" in href:
        return None
    if not href.startswith("/"):
        return None
    for prefix in _IGNORED_PREFIXES:
        if href.startswith(prefix):
            return None

    slug = href.strip("/").lower()
    if not slug or not _SLUG_RE.fullmatch(slug):
        return None
    return slug


def _dedupe(matches: list[SearchMatch]) -> list[SearchMatch]:
    seen: set[str] = set()
    output: list[SearchMatch] = []
    for item in matches:
        if item.slug in seen:
            continue
        seen.add(item.slug)
        output.append(item)
    return output


def parse_search_results(html: str) -> list[SearchMatch]:
    """Parse search matches using a primary strategy and a defensive fallback."""
    doc = parse_document(html)

    matches: list[SearchMatch] = []

    # Strategy S1: likely search result containers.
    for selector in (
        ".search-results a[href]",
        ".search-result a[href]",
        ".feature-list a[href]",
        ".features-list a[href]",
        "main a[href]",
    ):
        for anchor in all_nodes(doc, selector):
            href = attr(anchor, "href")
            slug = _slug_from_href(href)
            title = text(anchor)
            if slug and len(title) >= 3:
                matches.append(SearchMatch(slug=slug, title=title, href=href or f"/{slug}"))
        if matches:
            break

    # Strategy S2 fallback: site-local feature anchors.
    if not matches:
        for anchor in all_nodes(doc, "a[href]"):
            href = attr(anchor, "href")
            slug = _slug_from_href(href)
            title = text(anchor)
            if not slug or len(title) < 3:
                continue
            matches.append(SearchMatch(slug=slug, title=title, href=href or f"/{slug}"))

    return _dedupe(matches)
