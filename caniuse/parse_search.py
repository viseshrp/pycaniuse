"""Search result parser for caniuse search pages."""

from __future__ import annotations

import re

from .exceptions import CaniuseError
from .http import fetch_search_feature_ids, fetch_support_data
from .model import SearchMatch
from .util.html import all_nodes, attr, first, parse_document, text

_SLUG_RE = re.compile(r"^[a-z0-9_-]+$")
_SEARCH_TITLE_RE = re.compile(r"<title>\s*\"([^\"]+)\"\s+\|\s+Can I use", re.IGNORECASE)
_IGNORED_PREFIXES = (
    "/ciu/",
    "/issue-list",
    "/about",
    "/news",
    "/compare",
    "/process/",
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


def _extract_search_query(doc: object, html: str) -> str | None:
    title_match = _SEARCH_TITLE_RE.search(html)
    if title_match:
        query = title_match.group(1).strip()
        return query or None

    # Fallback for markup where title extraction is unavailable.
    if not all_nodes(doc, ".section__search-results"):
        return None

    search_input = first(doc, "#feat_search")
    query = attr(search_input, "value")
    if not query:
        return None
    normalized = query.strip()
    return normalized or None


def _parse_api_matches(query: str) -> list[SearchMatch]:
    try:
        feature_ids = fetch_search_feature_ids(query)
    except CaniuseError:
        return []
    if not feature_ids:
        return []

    title_by_id: dict[str, str] = {}
    try:
        payload = fetch_support_data(full_data_feats=feature_ids)
    except CaniuseError:
        payload = {}

    full_data = payload.get("fullData")
    if isinstance(full_data, list):
        for entry in full_data:
            if not isinstance(entry, dict):
                continue
            feature_id = entry.get("id")
            title = entry.get("title")
            if not isinstance(feature_id, str) or not isinstance(title, str):
                continue
            normalized_id = feature_id.strip().lower()
            normalized_title = title.strip()
            if normalized_id and normalized_title:
                title_by_id[normalized_id] = normalized_title

    matches: list[SearchMatch] = []
    for feature_id in feature_ids:
        if not _SLUG_RE.fullmatch(feature_id):
            continue
        title = title_by_id.get(feature_id) or feature_id
        matches.append(SearchMatch(slug=feature_id, title=title, href=f"/{feature_id}"))
    return matches


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

    query = _extract_search_query(doc, html)
    if query:
        api_matches = _parse_api_matches(query)
        if api_matches:
            return _dedupe(api_matches + matches)

    return _dedupe(matches)
