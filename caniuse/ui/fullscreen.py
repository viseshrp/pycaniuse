"""Full-mode renderer styled to resemble caniuse.com using Rich only."""

from __future__ import annotations

import re
import sys
import textwrap

from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..constants import STATUS_ICON_MAP, STATUS_LABEL_MAP
from ..model import BrowserSupportBlock, FeatureFull, SupportRange
from ..util.text import extract_note_markers

_STATUS_STYLE_MAP = {
    "y": "black on green3",
    "n": "white on red3",
    "a": "black on khaki1",
    "u": "black on grey70",
}
_ERA_STYLE_MAP = {
    "past": "dim",
    "current": "bold cyan",
    "future": "magenta",
}
_GLOBAL_USAGE_RE = re.compile(r"Global usage:\s*([0-9]+(?:\.[0-9]+)?)%")
_TITLE_DETAILS_RE = re.compile(r"Global usage:\s*[0-9]+(?:\.[0-9]+)?%\s*-\s*(.+)")
_NEWS_BANNER = "January 10, 2026 - New feature: CSS Grid Lanes"


def _support_lines(feature: FeatureFull) -> list[str]:
    lines: list[str] = []
    for block in feature.browser_blocks:
        lines.append(block.browser_name)
        for support_range in block.ranges:
            icon = STATUS_ICON_MAP.get(support_range.status, STATUS_ICON_MAP["u"])
            markers = extract_note_markers(support_range.raw_classes)
            marker_tail = f" [notes: {','.join(markers)}]" if markers else ""
            lines.append(f"  {icon} {support_range.range_text}{marker_tail}")
        lines.append("")
    return lines or ["No browser support blocks found."]


def _feature_lines(feature: FeatureFull) -> list[str]:
    lines: list[str] = [feature.title]

    if feature.spec_url:
        suffix = f" [{feature.spec_status}]" if feature.spec_status else ""
        lines.append(f"Spec: {feature.spec_url}{suffix}")

    usage_parts: list[str] = []
    if feature.usage_supported is not None:
        usage_parts.append(f"✅ {feature.usage_supported:.2f}%")
    if feature.usage_partial is not None:
        usage_parts.append(f"◐ {feature.usage_partial:.2f}%")
    if feature.usage_total is not None:
        usage_parts.append(f"Total {feature.usage_total:.2f}%")
    if usage_parts:
        lines.append("Usage: " + "  ".join(usage_parts))

    if feature.description_text:
        lines.extend(["", "Description", feature.description_text])

    lines.extend(["", "Browser Support", ""])
    lines.extend(_support_lines(feature))

    if feature.notes_text:
        lines.extend(["Notes", feature.notes_text, ""])

    if feature.resources:
        lines.append("Resources")
        for label, url in feature.resources:
            lines.append(f"- {label}: {url}")
        lines.append("")

    if feature.subfeatures:
        lines.append("Sub-features")
        for label, url in feature.subfeatures:
            lines.append(f"- {label}: {url}")
        lines.append("")

    lines.extend(_legend_lines())
    return lines


def _legend_lines() -> list[str]:
    return [
        "Legend",
        f"- {STATUS_ICON_MAP['y']} = {STATUS_LABEL_MAP['y']}",
        f"- {STATUS_ICON_MAP['n']} = {STATUS_LABEL_MAP['n']}",
        f"- {STATUS_ICON_MAP['a']} = {STATUS_LABEL_MAP['a']}",
        f"- {STATUS_ICON_MAP['u']} = {STATUS_LABEL_MAP['u']}",
    ]


def _wrap_line(value: str, width: int) -> list[str]:
    if not value:
        return [""]
    indent_len = len(value) - len(value.lstrip(" "))
    indent = " " * indent_len
    content = value[indent_len:]
    target_width = max(width - indent_len, 20)
    wrapped = textwrap.wrap(content, width=target_width) or [""]
    return [f"{indent}{line}" for line in wrapped]


def _render_lines(feature: FeatureFull, width: int) -> list[str]:
    lines: list[str] = []
    for source_line in _feature_lines(feature):
        lines.extend(_wrap_line(source_line, width))
    return lines


def _tab_sections(feature: FeatureFull) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    info_lines: list[str] = []
    if feature.spec_url:
        suffix = f" ({feature.spec_status})" if feature.spec_status else ""
        info_lines.append(f"Spec: {feature.spec_url}{suffix}")

    usage_parts: list[str] = []
    if feature.usage_supported is not None:
        usage_parts.append(f"✅ {feature.usage_supported:.2f}%")
    if feature.usage_partial is not None:
        usage_parts.append(f"◐ {feature.usage_partial:.2f}%")
    if feature.usage_total is not None:
        usage_parts.append(f"Total {feature.usage_total:.2f}%")
    if usage_parts:
        info_lines.append("Usage: " + "  ".join(usage_parts))
    if feature.description_text:
        info_lines.extend(["", "Description", feature.description_text])
    if not info_lines:
        info_lines = ["No additional feature metadata."]
    sections.append(("Info", info_lines))

    if feature.tabs:
        for tab_name, tab_content in feature.tabs.items():
            tab_lines = tab_content.splitlines() or [tab_content]
            sections.append((tab_name, tab_lines))
    else:
        if feature.notes_text:
            sections.append(("Notes", [feature.notes_text]))
        if feature.resources:
            sections.append(
                ("Resources", [f"- {label}: {url}" for label, url in feature.resources])
            )
        if feature.subfeatures:
            sections.append(
                ("Sub-features", [f"- {label}: {url}" for label, url in feature.subfeatures])
            )

    sections.append(("Legend", _legend_lines()[1:]))
    return sections


def _era_label(support_range: SupportRange) -> str:
    if support_range.is_current:
        return "current"
    if support_range.is_future:
        return "future"
    return "past"


def _extract_global_usage(title_attr: str) -> str | None:
    if not title_attr:
        return None
    match = _GLOBAL_USAGE_RE.search(title_attr)
    if not match:
        return None
    return f"{match.group(1)}%"


def _extract_title_details(title_attr: str) -> str | None:
    if not title_attr:
        return None
    match = _TITLE_DETAILS_RE.search(title_attr)
    if not match:
        return None
    return match.group(1)


def _format_support_line(support_range: SupportRange, *, include_usage: bool) -> Text:
    icon = STATUS_ICON_MAP.get(support_range.status, STATUS_ICON_MAP["u"])
    status_label = STATUS_LABEL_MAP.get(support_range.status, STATUS_LABEL_MAP["u"])
    status_style = _STATUS_STYLE_MAP.get(support_range.status, _STATUS_STYLE_MAP["u"])
    notes = extract_note_markers(support_range.raw_classes)
    era = _era_label(support_range)
    era_style = _ERA_STYLE_MAP.get(era, "dim")
    usage = _extract_global_usage(support_range.title_attr) if include_usage else None

    line = Text()
    line.append(f" {icon} ", style=status_style)
    line.append(f" {support_range.range_text} ", style="bold")
    line.append(f"[{era}]", style=era_style)
    line.append(f"  {status_label}", style="dim")
    if usage:
        line.append(f"  usage:{usage}", style="dim")
    if notes:
        line.append(f"  notes:{','.join(notes)}", style="yellow")
    return line


def _top_nav_panel() -> Panel:
    nav = Text()
    nav.append("Home", style="bold cyan")
    nav.append("   News", style="bold cyan")
    nav.append("   Compare browsers", style="bold cyan")
    nav.append("   About", style="bold cyan")

    search = Text()
    search.append("Can I use ", style="bold")
    search.append(" Search ", style="black on white")
    search.append(" ? ", style="bold")
    search.append(" Settings ", style="black on grey70")

    news = Text(_NEWS_BANNER, style="yellow")
    return Panel(Group(nav, Text(""), news, Text(""), search), border_style="grey50")


def _feature_intro_panel(feature: FeatureFull, width: int) -> Panel:
    heading = Text(feature.title, style="bold")
    if feature.spec_status:
        heading.append("  ")
        heading.append(f"- {feature.spec_status}", style="cyan")

    usage = Text("Global usage ", style="bold")
    if feature.usage_supported is not None:
        usage.append(f" {feature.usage_supported:.2f}% ", style=_STATUS_STYLE_MAP["y"])
    if feature.usage_partial is not None:
        usage.append(" + ", style="dim")
        usage.append(f" {feature.usage_partial:.2f}% ", style=_STATUS_STYLE_MAP["a"])
    if feature.usage_total is not None:
        usage.append(" = ", style="dim")
        usage.append(f"{feature.usage_total:.2f}%", style="bold")

    desc_width = max(width - 12, 35)
    description = feature.description_text or "No description available."
    wrapped_desc = textwrap.fill(description, width=desc_width)

    payload: list[RenderableType] = [heading]
    if feature.spec_url:
        payload.append(Text(feature.spec_url, style="cyan"))
    payload.extend([Text(""), usage, Text(""), Text(wrapped_desc)])
    return Panel(Group(*payload), title="Feature", border_style="white")


def _browser_card(block: BrowserSupportBlock) -> Panel:
    rows: list[RenderableType] = []
    if not block.ranges:
        rows.append(Text("No support data", style="dim"))
        return Panel(Group(*rows), title=block.browser_name, border_style="grey50")

    for support_range in block.ranges:
        rows.append(_format_support_line(support_range, include_usage=False))
        usage = _extract_global_usage(support_range.title_attr)
        details = _extract_title_details(support_range.title_attr)
        meta = Text()
        if usage:
            meta.append(f"  Global usage: {usage}", style="dim")
        if details:
            if usage:
                meta.append(" - ", style="dim")
            meta.append(details, style="dim")
        if meta.plain:
            rows.append(meta)
    return Panel(Group(*rows), title=block.browser_name, border_style="grey50")


def _support_columns_panel(feature: FeatureFull) -> Panel:
    if not feature.browser_blocks:
        return Panel(Text("No browser support blocks found."), title="Support", border_style="red")

    cards = [_browser_card(block) for block in feature.browser_blocks]
    return Panel(Columns(cards, expand=True), title="Support", border_style="green")


def _notes_resources_panel(feature: FeatureFull) -> Panel:
    rows: list[RenderableType] = []

    if feature.notes_text:
        rows.append(Text("Notes", style="bold"))
        rows.append(Text(feature.notes_text))
        rows.append(Text(""))

    if feature.resources:
        rows.append(Text("Resources", style="bold"))
        for label, url in feature.resources:
            rows.append(Text(f"- {label}: {url}"))
        rows.append(Text(""))

    if feature.subfeatures:
        rows.append(Text("Sub-features", style="bold"))
        for label, url in feature.subfeatures:
            rows.append(Text(f"- {label}: {url}"))
        rows.append(Text(""))

    if not rows:
        rows.append(Text("No notes, resources, or sub-features available.", style="dim"))

    return Panel(Group(*rows), title="Additional Information", border_style="blue")


def _site_footer_panel() -> Panel:
    left = Group(
        Text("Can I use...", style="bold"),
        Text("Browser support tables for modern web technologies", style="dim"),
        Text("Created & maintained by @Fyrd, design by @Lensco.", style="dim"),
    )
    right = Group(
        Text("Site links", style="bold"),
        Text("Home  |  Feature index  |  Usage table  |  Feature suggestions"),
        Text("Caniuse data on GitHub", style="cyan"),
    )
    grid = Table.grid(expand=True)
    grid.add_column(ratio=2)
    grid.add_column(ratio=2)
    grid.add_row(left, right)
    return Panel(grid, border_style="grey50")


def _legend_panel() -> Panel:
    legend = Text()
    legend.append(" ")
    legend.append(f" {STATUS_ICON_MAP['y']} Supported ", style=_STATUS_STYLE_MAP["y"])
    legend.append(" ")
    legend.append(f" {STATUS_ICON_MAP['n']} Not supported ", style=_STATUS_STYLE_MAP["n"])
    legend.append(" ")
    legend.append(f" {STATUS_ICON_MAP['a']} Partial ", style=_STATUS_STYLE_MAP["a"])
    legend.append(" ")
    legend.append(f" {STATUS_ICON_MAP['u']} Unknown ", style=_STATUS_STYLE_MAP["u"])

    controls = Text(
        "Use pager controls to scroll full output (press q to exit pager).",
        style="dim",
    )
    return Panel(Group(controls, legend), title="Legend", border_style="grey50")


def _build_full_renderable(feature: FeatureFull, width: int) -> Group:
    return Group(
        _top_nav_panel(),
        Text(""),
        _feature_intro_panel(feature, width),
        Text(""),
        _support_columns_panel(feature),
        Text(""),
        _notes_resources_panel(feature),
        Text(""),
        _site_footer_panel(),
        Text(""),
        _legend_panel(),
    )


def run_fullscreen(feature: FeatureFull) -> None:
    """Render full mode using Rich renderables and pager when available."""
    console = Console()
    renderable = _build_full_renderable(feature, console.size.width)

    if sys.stdin.isatty() and sys.stdout.isatty() and hasattr(console, "pager"):
        with console.pager(styles=True):
            console.print(renderable)
        return

    console.print(renderable)
