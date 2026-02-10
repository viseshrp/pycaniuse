"""Feature page parser (basic + full)."""

from __future__ import annotations

from collections import OrderedDict
import json
import re
from typing import Literal, cast

from .constants import BASE_URL, BASIC_MODE_BROWSERS
from .exceptions import CaniuseError
from .http import fetch_feature_aux_data, fetch_support_data
from .model import BrowserSupportBlock, FeatureBasic, FeatureFull, SupportRange
from .util.html import (
    all_nodes,
    attr,
    class_tokens,
    first,
    markdown_text,
    parse_document,
    safe_join_url,
    text,
)
from .util.text import parse_percent

_STATUS_CLASS_ORDER: tuple[Literal["y", "n", "a", "u"], ...] = ("y", "n", "a", "u")
_INITIAL_FEAT_DATA_RE = re.compile(
    r'window\.initialFeatData\s*=\s*\{id:\s*"(?P<id>[^"]+)",\s*data:\s*"(?P<data>.*?)"\s*\};',
    re.DOTALL,
)


def _parse_title(doc: object, slug: str) -> str:
    title_node = first(doc, ".feature-title")
    title = text(title_node)
    if title:
        return title

    fallback_title = text(first(doc, "title"))
    if fallback_title:
        return fallback_title.split("| Can I use", maxsplit=1)[0].strip()
    return slug


def _parse_spec(doc: object) -> tuple[str | None, str | None]:
    spec = first(doc, "a.specification")
    if spec is None:
        return None, None

    spec_url = safe_join_url(BASE_URL, attr(spec, "href"))
    visible = text(spec)
    status = None
    if "-" in visible:
        tail = visible.rsplit("-", maxsplit=1)[-1].strip()
        status = tail or None
    if not status:
        classes = class_tokens(spec)
        for token in classes:
            if token not in {"specification"} and token.isalpha() and len(token) <= 4:
                status = token.upper()
                break

    return spec_url, status


def _parse_usage(doc: object) -> tuple[float | None, float | None, float | None]:
    usage_node = first(doc, 'li.support-stats[data-usage-id="region.global"]')
    if usage_node is None:
        return None, None, None
    supported = parse_percent(text(first(usage_node, ".support")))
    partial = parse_percent(text(first(usage_node, ".partial")))
    total = parse_percent(text(first(usage_node, ".total")))
    return supported, partial, total


def _parse_description(doc: object) -> str:
    description_node = first(doc, ".feature-description")
    if description_node is None:
        return ""
    markdown = markdown_text(description_node)
    return markdown if markdown else text(description_node)


def _parse_support_blocks(doc: object, *, include_all: bool) -> list[BrowserSupportBlock]:
    support_nodes = all_nodes(doc, ".support-container .support-list")
    output: list[BrowserSupportBlock] = []

    for support in support_nodes:
        heading = first(support, "h4.browser-heading")
        browser_name = text(heading)
        if not browser_name:
            continue

        browser_key = ""
        for token in class_tokens(heading):
            if token.startswith("browser--"):
                browser_key = token.replace("browser--", "", 1)
                break
        if not browser_key:
            browser_key = browser_name.lower().replace(" ", "-")

        ranges: list[SupportRange] = []
        for stat_cell in all_nodes(support, "ol > li.stat-cell"):
            classes = class_tokens(stat_cell)
            status: Literal["y", "n", "a", "u"] = "u"
            for token in _STATUS_CLASS_ORDER:
                if token in classes:
                    status = token
                    break

            range_text = _parse_support_range_text(stat_cell)
            if not range_text:
                continue

            ranges.append(
                SupportRange(
                    range_text=range_text,
                    status=status,
                    is_past="past" in classes,
                    is_current="current" in classes,
                    is_future="future" in classes,
                    title_attr=attr(stat_cell, "title") or "",
                    raw_classes=classes,
                )
            )

        block = BrowserSupportBlock(
            browser_name=browser_name,
            browser_key=browser_key,
            ranges=ranges,
        )
        output.append(block)

    if include_all:
        return output
    return [block for block in output if block.browser_key in BASIC_MODE_BROWSERS]


def _parse_support_range_text(stat_cell: object) -> str:
    """Extract only the version range text from a support list cell."""
    children = list(getattr(stat_cell, "children", []))
    text_parts: list[str] = []
    for child in children:
        if getattr(child, "name", None) == "#text":
            child_text = text(child)
            if child_text:
                text_parts.append(child_text)
    if text_parts:
        return " ".join(text_parts).strip()

    raw = text(stat_cell)
    if not raw:
        return ""
    if " : " in raw:
        return raw.split(" : ", maxsplit=1)[0].split(maxsplit=1)[-1]
    return raw


def _parse_notes(doc: object) -> str | None:
    notes_node = first(doc, "div.single-page__notes")
    if notes_node is None:
        return None
    notes = markdown_text(notes_node) or text(notes_node)
    return notes or None


def _parse_resources(doc: object) -> list[tuple[str, str]]:
    resources: list[tuple[str, str]] = []
    for anchor in all_nodes(doc, "dl.single-feat-resources dd a"):
        href = safe_join_url(BASE_URL, attr(anchor, "href"))
        label = text(anchor)
        if href and label:
            resources.append((label, href))
    return resources


def _parse_subfeatures(doc: object) -> list[tuple[str, str]]:
    subfeatures: list[tuple[str, str]] = []

    for dl in all_nodes(doc, "dl"):
        children = list(getattr(dl, "children", []))
        collecting = False
        for child in children:
            child_name = getattr(child, "name", None)
            if child_name == "dt":
                collecting = text(child).rstrip(":").strip().lower() == "sub-features"
                continue
            if child_name == "dd" and collecting:
                for anchor in all_nodes(child, "a"):
                    href = safe_join_url(BASE_URL, attr(anchor, "href"))
                    label = text(anchor)
                    if href and label:
                        subfeatures.append((label, href))

    return subfeatures


def _parse_initial_feature_data(html: str) -> dict[str, object] | None:
    match = _INITIAL_FEAT_DATA_RE.search(html)
    if match is None:
        return None

    raw_data = match.group("data")
    try:
        decoded = json.loads(f'"{raw_data}"')
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, list) or not payload:
        return None
    first_item = payload[0]
    if not isinstance(first_item, dict):
        return None
    return first_item


def _clean_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lstrip("≤").strip()
    return cleaned or None


def _parse_baseline_fields(data: dict[str, object]) -> tuple[str | None, str | None, str | None]:
    baseline = data.get("baseline_status")
    if not isinstance(baseline, dict):
        baseline = data.get("baselineStatus")
    if not isinstance(baseline, dict):
        return None, None, None
    baseline_map = cast(dict[str, object], baseline)

    raw_status = baseline_map.get("status")
    status = raw_status.strip().lower() if isinstance(raw_status, str) else None
    low_date = _clean_date(baseline_map.get("lowDate") or baseline_map.get("low_date"))
    high_date = _clean_date(baseline_map.get("highDate") or baseline_map.get("high_date"))
    return status, low_date, high_date


def _parse_baseline_from_metadata(
    payload: dict[str, object],
    slug: str,
) -> tuple[str | None, str | None, str | None]:
    meta_data = payload.get("metaData")
    if not isinstance(meta_data, list):
        return None, None, None

    for item in meta_data:
        if not isinstance(item, dict):
            continue
        item_map = cast(dict[str, object], item)
        item_id = item_map.get("id")
        if not isinstance(item_id, str) or item_id.strip().lower() != slug:
            continue
        raw_status = item_map.get("baselineStatus")
        status = raw_status.strip().lower() if isinstance(raw_status, str) else None
        low_date = _clean_date(item_map.get("baselineLowDate"))
        high_date = _clean_date(item_map.get("baselineHighDate"))
        return status, low_date, high_date

    return None, None, None


def _parse_known_issues(entries: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    for entry in entries:
        description = entry.get("description")
        if isinstance(description, str):
            cleaned = description.strip()
            if cleaned:
                issues.append(cleaned)
    return issues


def _parse_numbered_notes(data: dict[str, object] | None) -> list[str]:
    if not isinstance(data, dict):
        return []
    raw_notes = data.get("notes_by_num")
    if not isinstance(raw_notes, dict):
        raw_notes = data.get("notesByNum")
    if not isinstance(raw_notes, dict):
        return []

    def _note_sort_key(item: tuple[object, object]) -> tuple[int, str]:
        key = str(item[0]).strip()
        if key.isdigit():
            return (0, f"{int(key):08d}")
        return (1, key)

    output: list[str] = []
    for key_obj, value in sorted(raw_notes.items(), key=_note_sort_key):
        key = str(key_obj).strip()
        if not key:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                output.append(f"[{key}] {cleaned}")
    return output


def _parse_resource_entries(entries: list[dict[str, object]]) -> list[tuple[str, str]]:
    resources: list[tuple[str, str]] = []
    for entry in entries:
        title = entry.get("title")
        url = entry.get("url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        cleaned_title = title.strip()
        cleaned_url = safe_join_url(BASE_URL, url.strip())
        if cleaned_title and cleaned_url:
            resources.append((cleaned_title, cleaned_url))
    return resources


def _parse_subfeatures_from_initial_data(data: dict[str, object]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    raw_items = data.get("children")
    if not isinstance(raw_items, list):
        raw_items = data.get("bcd_features")
    if not isinstance(raw_items, list):
        return output

    seen: set[str] = set()
    for item in raw_items:
        feature_id: str | None = None
        title: str | None = None
        if isinstance(item, str):
            feature_id = item.strip().lower()
        elif isinstance(item, dict):
            item_map = cast(dict[str, object], item)
            raw_id = item_map.get("id")
            if isinstance(raw_id, str):
                feature_id = raw_id.strip().lower()
            raw_title = item_map.get("title")
            if isinstance(raw_title, str):
                title = raw_title.strip()

        if not feature_id:
            continue
        href = safe_join_url(BASE_URL, f"/{feature_id}")
        if not href or href in seen:
            continue
        seen.add(href)
        output.append((title or feature_id, href))

    return output


def _is_primary_ciu_feature(slug: str) -> bool:
    return not slug.startswith("mdn-") and not slug.startswith("wf-")


def _is_mdn_feature(slug: str) -> bool:
    return slug.startswith("mdn-")


def _is_wf_feature(slug: str) -> bool:
    return slug.startswith("wf-")


def _build_baseline_note(
    status: str | None,
    low_date: str | None,
    high_date: str | None,
) -> str | None:
    if status not in {"high", "low"}:
        return None
    since_date = low_date or high_date
    if since_date:
        try:
            year, month, _day = since_date.split("-")
            month_name = (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            )[max(1, min(12, int(month))) - 1]
        except (ValueError, IndexError):
            return "This feature works across the latest devices and major browser versions."
        return (
            f"Since {month_name} {year}, this feature works across the latest devices and "
            "major browser versions."
        )
    return "This feature works across the latest devices and major browser versions."


def _build_mdn_attribution_note(initial_data: dict[str, object] | None) -> str | None:
    if not isinstance(initial_data, dict):
        return None

    mdn_url = initial_data.get("mdn_url")
    path = initial_data.get("path")
    lines = ["Support data for this feature provided by MDN browser-compat-data."]
    if isinstance(mdn_url, str) and mdn_url.strip():
        lines.append(f"MDN reference: {mdn_url.strip()}")
    if isinstance(path, str) and path.strip():
        lines.append(
            f"Source data: https://github.com/mdn/browser-compat-data/blob/main/{path.strip()}"
        )
    return "\n".join(lines) if lines else None


def _build_wf_attribution_note(slug: str) -> str:
    feature_id = slug.removeprefix("wf-")
    return (
        "Support data for this feature provided by the web-features project.\n"
        "Contributing docs: "
        "https://github.com/web-platform-dx/web-features/blob/main/docs/CONTRIBUTING.md\n"
        f"Feature source: https://github.com/web-platform-dx/web-features/blob/main/features/{feature_id}.yml"
    )


def parse_feature_basic(html: str, slug: str) -> FeatureBasic:
    """Parse feature page content for basic mode."""
    doc = parse_document(html)

    spec_url, spec_status = _parse_spec(doc)
    usage_supported, usage_partial, usage_total = _parse_usage(doc)
    browser_blocks = _parse_support_blocks(doc, include_all=False)

    parse_warnings: list[str] = []
    if not browser_blocks:
        parse_warnings.append("support")

    return FeatureBasic(
        slug=slug,
        title=_parse_title(doc, slug),
        spec_url=spec_url,
        spec_status=spec_status,
        usage_supported=usage_supported,
        usage_partial=usage_partial,
        usage_total=usage_total,
        description_text=_parse_description(doc),
        browser_blocks=browser_blocks,
        parse_warnings=parse_warnings,
    )


def parse_feature_full(html: str, slug: str) -> FeatureFull:
    """Parse feature page content for full-screen mode."""
    doc = parse_document(html)
    normalized_slug = slug.strip().lower()
    initial_data = _parse_initial_feature_data(html)

    spec_url, spec_status = _parse_spec(doc)
    usage_supported, usage_partial, usage_total = _parse_usage(doc)
    browser_blocks = _parse_support_blocks(doc, include_all=True)

    notes_text = _parse_notes(doc)
    if not notes_text and isinstance(initial_data, dict):
        initial_notes = initial_data.get("notes")
        if isinstance(initial_notes, str) and initial_notes.strip():
            notes_text = initial_notes.strip()
    numbered_notes = _parse_numbered_notes(initial_data)

    known_issues: list[str] = []
    resources = _parse_resources(doc)
    subfeatures = _parse_subfeatures(doc)
    baseline_status: str | None = None
    baseline_low_date: str | None = None
    baseline_high_date: str | None = None

    if isinstance(initial_data, dict):
        if not subfeatures:
            subfeatures = _parse_subfeatures_from_initial_data(initial_data)

        baseline_status, baseline_low_date, baseline_high_date = _parse_baseline_fields(
            initial_data
        )

        if _is_primary_ciu_feature(normalized_slug):
            bug_count = initial_data.get("bug_count")
            if isinstance(bug_count, int) and bug_count > 0:
                try:
                    known_issues = _parse_known_issues(
                        fetch_feature_aux_data(normalized_slug, "bugs")
                    )
                except CaniuseError:
                    known_issues = []

            link_count = initial_data.get("link_count")
            should_fetch_links = isinstance(link_count, int) and link_count >= 0
            if should_fetch_links or not resources:
                try:
                    api_resources = _parse_resource_entries(
                        fetch_feature_aux_data(normalized_slug, "links")
                    )
                    if api_resources:
                        resources = api_resources
                except CaniuseError:
                    pass

        if baseline_status is None:
            try:
                metadata_payload = fetch_support_data(meta_data_feats=[normalized_slug])
            except CaniuseError:
                metadata_payload = {}
            baseline_status, baseline_low_date, baseline_high_date = _parse_baseline_from_metadata(
                metadata_payload,
                normalized_slug,
            )

    baseline_note = _build_baseline_note(baseline_status, baseline_low_date, baseline_high_date)
    notes_parts: list[str] = []
    if _is_mdn_feature(normalized_slug):
        if notes_text:
            notes_parts.append(notes_text)
        if numbered_notes:
            notes_parts.append("\n".join(numbered_notes))
        mdn_note = _build_mdn_attribution_note(initial_data)
        if mdn_note:
            notes_parts.append(mdn_note)
    elif _is_wf_feature(normalized_slug):
        if baseline_note:
            notes_parts.append(baseline_note)
        if notes_text:
            notes_parts.append(notes_text)
        if numbered_notes:
            notes_parts.append("\n".join(numbered_notes))
        notes_parts.append(_build_wf_attribution_note(normalized_slug))
    else:
        if baseline_note:
            notes_parts.append(baseline_note)
        if notes_text:
            notes_parts.append(notes_text)
        if numbered_notes:
            notes_parts.append("\n".join(numbered_notes))

    notes_tab_text = "\n\n".join([part for part in notes_parts if part.strip()]) or None

    tabs: OrderedDict[str, str] = OrderedDict()
    if notes_tab_text:
        tabs["Notes"] = notes_tab_text
    if known_issues:
        tabs["Known issues"] = "\n".join([f"- {item}" for item in known_issues])
    if resources:
        tabs["Resources"] = "\n".join([f"- {label}: {url}" for label, url in resources])
    if subfeatures:
        tabs["Sub-features"] = "\n".join([f"- {label}: {url}" for label, url in subfeatures])

    parse_warnings: list[str] = []
    if not browser_blocks:
        parse_warnings.append("support")

    return FeatureFull(
        slug=slug,
        title=_parse_title(doc, slug),
        spec_url=spec_url,
        spec_status=spec_status,
        usage_supported=usage_supported,
        usage_partial=usage_partial,
        usage_total=usage_total,
        description_text=_parse_description(doc),
        browser_blocks=browser_blocks,
        parse_warnings=parse_warnings,
        notes_text=notes_text,
        known_issues=known_issues,
        resources=resources,
        subfeatures=subfeatures,
        baseline_status=baseline_status,
        baseline_low_date=baseline_low_date,
        baseline_high_date=baseline_high_date,
        tabs=dict(tabs),
    )
