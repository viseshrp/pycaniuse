"""Feature page parser (basic + full)."""

from __future__ import annotations

from collections import OrderedDict

from .constants import BASE_URL, BASIC_MODE_BROWSERS
from .model import BrowserSupportBlock, FeatureBasic, FeatureFull, SupportRange
from .util.html import all_nodes, attr, class_tokens, first, markdown_text, parse_document, safe_join_url, text
from .util.text import parse_percent

_STATUS_CLASS_ORDER = ("y", "n", "a", "u")


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
            status = "u"
            for token in _STATUS_CLASS_ORDER:
                if token in classes:
                    status = token
                    break

            range_text = text(stat_cell)
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

    spec_url, spec_status = _parse_spec(doc)
    usage_supported, usage_partial, usage_total = _parse_usage(doc)
    browser_blocks = _parse_support_blocks(doc, include_all=True)

    notes_text = _parse_notes(doc)
    resources = _parse_resources(doc)
    subfeatures = _parse_subfeatures(doc)

    tabs: "OrderedDict[str, str]" = OrderedDict()
    if notes_text:
        tabs["Notes"] = notes_text
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
        resources=resources,
        subfeatures=subfeatures,
        tabs=dict(tabs),
    )
