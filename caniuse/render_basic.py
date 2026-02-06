"""Basic mode renderer."""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from .constants import FULL_MODE_HINT, STATUS_ICON_MAP, STATUS_LABEL_MAP
from .model import FeatureBasic
from .util.text import extract_note_markers


def _usage_line(feature: FeatureBasic) -> str | None:
    if (
        feature.usage_supported is None
        and feature.usage_partial is None
        and feature.usage_total is None
    ):
        return None

    parts: list[str] = []
    if feature.usage_supported is not None:
        parts.append(f"✅ {feature.usage_supported:.2f}%")
    if feature.usage_partial is not None:
        parts.append(f"◐ {feature.usage_partial:.2f}%")
    if feature.usage_total is not None:
        parts.append(f"Total: {feature.usage_total:.2f}%")
    return "Usage: " + "  ".join(parts)


def render_basic(feature: FeatureBasic) -> Group:
    """Render basic feature details as a Rich renderable group."""
    lines: list[Text] = []

    lines.append(Text(feature.title, style="bold"))

    if feature.spec_url:
        spec_tail = f" [{feature.spec_status}]" if feature.spec_status else ""
        lines.append(Text(f"Spec: {feature.spec_url}{spec_tail}"))

    usage_line = _usage_line(feature)
    if usage_line:
        lines.append(Text(usage_line))

    if feature.description_text:
        lines.append(Text(""))
        lines.append(Text("Description", style="bold"))
        lines.append(Text(feature.description_text))

    lines.append(Text(""))
    lines.append(Text("Browser Support", style="bold"))

    for block in feature.browser_blocks:
        lines.append(Text(f"{block.browser_name}", style="bold cyan"))
        for support_range in block.ranges:
            status_icon = STATUS_ICON_MAP.get(support_range.status, STATUS_ICON_MAP["u"])
            status_label = STATUS_LABEL_MAP.get(support_range.status, STATUS_LABEL_MAP["u"])
            notes = extract_note_markers(support_range.raw_classes)
            note_hint = f" [See notes: {','.join(notes)}]" if notes else ""
            lines.append(
                Text(f"  {support_range.range_text}: {status_icon} {status_label}{note_hint}")
            )

    lines.append(Text(""))
    lines.append(Text(FULL_MODE_HINT, style="dim"))

    return Group(Panel(Group(*lines), border_style="blue", title=f"/{feature.slug}"))
