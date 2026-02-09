"""Full-mode renderer powered by Rich primitives only."""

from __future__ import annotations

import re
import sys
import textwrap

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..constants import STATUS_ICON_MAP, STATUS_LABEL_MAP
from ..model import FeatureFull, SupportRange
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
    line.append(f" {support_range.range_text} ")
    line.append(f"[{era}]", style=era_style)
    line.append(f"  {status_label}", style="dim")
    if usage:
        line.append(f"  usage:{usage}", style="dim")
    if notes:
        line.append(f"  notes:{','.join(notes)}", style="yellow")
    return line


def _support_table(feature: FeatureFull) -> Table:
    table = Table(expand=True, show_lines=False)
    table.add_column("Browser", style="bold")
    table.add_column("Range", justify="right")
    table.add_column("Status")
    table.add_column("Global Usage", justify="right")
    table.add_column("Notes", style="yellow")

    if not feature.browser_blocks:
        table.add_row("No browser support blocks found.", "-", "-", "-", "-")
        return table

    for block in feature.browser_blocks:
        if not block.ranges:
            table.add_row(block.browser_name, "-", "No range data", "-", "-")
            continue

        for idx, support_range in enumerate(block.ranges):
            usage = _extract_global_usage(support_range.title_attr) or "-"
            notes = extract_note_markers(support_range.raw_classes)
            browser_name = block.browser_name if idx == 0 else ""
            table.add_row(
                browser_name,
                support_range.range_text,
                _format_support_line(support_range, include_usage=False),
                usage,
                ",".join(notes) if notes else "-",
            )
    return table


def _feature_heading_panel(feature: FeatureFull, width: int) -> Panel:
    title_line = Text(feature.title, style="bold")
    if feature.spec_status:
        title_line.append("  ")
        title_line.append(f"- {feature.spec_status}", style="cyan")

    usage_line = Text("Global usage: ", style="bold")
    has_usage = False
    if feature.usage_supported is not None:
        usage_line.append(f" {feature.usage_supported:.2f}% ", style=_STATUS_STYLE_MAP["y"])
        usage_line.append(" + ", style="dim")
        has_usage = True
    if feature.usage_partial is not None:
        usage_line.append(f" {feature.usage_partial:.2f}% ", style=_STATUS_STYLE_MAP["a"])
        has_usage = True
    if feature.usage_total is not None:
        usage_line.append(f" = {feature.usage_total:.2f}%", style="bold")
        has_usage = True
    if not has_usage:
        usage_line.append("Unavailable", style="dim")

    desc_width = max(width - 8, 30)
    description_lines = []
    if feature.description_text:
        description_lines = textwrap.wrap(feature.description_text, width=desc_width)

    description = "No description available."
    if description_lines:
        description = "\n".join(description_lines[:4])

    body: list[Text] = [title_line]
    if feature.spec_url:
        body.append(Text(feature.spec_url, style="cyan"))
    body.extend([Text(""), usage_line, Text(""), Text(description)])
    return Panel(Group(*body), border_style="white", title=f"/{feature.slug}")


def _tab_sections_panel(feature: FeatureFull) -> Panel:
    sections: list[Text] = []
    for tab_name, tab_lines in _tab_sections(feature):
        sections.append(Text(tab_name, style="bold magenta"))
        for line in tab_lines:
            sections.append(Text(line))
        sections.append(Text(""))
    return Panel(Group(*sections), title="Feature Details", border_style="magenta")


def _footer_panel() -> Panel:
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
    return Panel(Group(controls, legend), border_style="grey50")


def _build_full_renderable(feature: FeatureFull, width: int) -> Group:
    return Group(
        _feature_heading_panel(feature, width),
        Text(""),
        Panel(_support_table(feature), title="Support Table", border_style="green"),
        Text(""),
        _tab_sections_panel(feature),
        Text(""),
        _footer_panel(),
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
