"""Rich render helpers and fullscreen orchestration for full feature output."""

from __future__ import annotations

from dataclasses import dataclass
import sys
import textwrap

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from ..constants import STATUS_ICON_MAP, STATUS_LABEL_MAP
from ..model import FeatureFull, SupportRange
from ..util.text import extract_note_markers

_BROWSER_TAB_WIDTH = 16
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


@dataclass
class _TuiState:
    selected_browser: int = 0
    browser_offset: int = 0
    browser_visible_count: int = 1
    range_scroll: int = 0
    tab_index: int = 0
    tab_scroll: int = 0


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
        lines.append("")
        lines.append("Description")
        lines.append(feature.description_text)

    lines.append("")
    lines.append("Browser Support")
    lines.append("")
    lines.extend(_support_lines(feature))

    if feature.known_issues:
        lines.append("Known issues")
        for issue in feature.known_issues:
            lines.append(f"- {issue}")
        lines.append("")

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
    allowed_tabs = {"known issues", "resources", "sub-features"}

    if feature.tabs:
        for tab_name, tab_content in feature.tabs.items():
            if tab_name.strip().lower() not in allowed_tabs:
                continue
            tab_lines = tab_content.splitlines() or [tab_content]
            sections.append((tab_name, tab_lines))
    else:
        if feature.known_issues:
            sections.append(("Known issues", [f"- {issue}" for issue in feature.known_issues]))
        if feature.resources:
            sections.append(
                ("Resources", [f"- {label}: {url}" for label, url in feature.resources])
            )
        if feature.subfeatures:
            sections.append(
                ("Sub-features", [f"- {label}: {url}" for label, url in feature.subfeatures])
            )

    if not sections:
        return [("Details", ["No known issues, resources, or sub-features available."])]
    return sections


def _era_label(support_range: SupportRange) -> str:
    if support_range.is_current:
        return "current"
    if support_range.is_future:
        return "future"
    return "past"


def _extract_global_usage(title_attr: str) -> str | None:
    marker = "Global usage:"
    if marker not in title_attr:
        return None
    usage = title_attr.split(marker, maxsplit=1)[1].strip()
    if not usage:
        return None
    first_token = usage.split(maxsplit=1)[0]
    return first_token if first_token.endswith("%") else None


def _linkify_line(value: str, *, base_style: str | None = None) -> Text:
    text = Text()
    tokens = value.split()
    for index, token in enumerate(tokens):
        rendered = token
        style = base_style

        if token.startswith("http://") or token.startswith("https://"):
            rendered = token
            style = "underline cyan" if not base_style else f"{base_style} underline cyan"
            text.append(rendered, style=f"{style} link {token}")
        elif token.startswith("[") and "](" in token and token.endswith(")"):
            label, rest = token[1:].split("](", maxsplit=1)
            url = rest[:-1]
            style = "underline cyan" if not base_style else f"{base_style} underline cyan"
            text.append(label, style=f"{style} link {url}")
        else:
            text.append(rendered, style=base_style)

        if index != len(tokens) - 1:
            text.append(" ", style=base_style)

    if not tokens:
        return Text(value, style=base_style or "")
    return text


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


def _fit_browser_window(state: _TuiState, browser_count: int, visible_count: int) -> None:
    if browser_count <= 0:
        state.selected_browser = 0
        state.browser_offset = 0
        return
    state.selected_browser = max(0, min(state.selected_browser, browser_count - 1))
    max_offset = max(browser_count - visible_count, 0)
    state.browser_offset = max(0, min(state.browser_offset, max_offset))
    if state.selected_browser < state.browser_offset:
        state.browser_offset = state.selected_browser
    if state.selected_browser >= state.browser_offset + visible_count:
        state.browser_offset = max(state.selected_browser - visible_count + 1, 0)


def _support_overview_panel(
    feature: FeatureFull, state: _TuiState, width: int, max_rows: int
) -> Panel:
    browser_count = len(feature.browser_blocks)
    visible_count = max(width // _BROWSER_TAB_WIDTH, 1)
    state.browser_visible_count = visible_count
    _fit_browser_window(state, browser_count, visible_count)
    if browser_count == 0:
        return Panel(
            Text("No browser support blocks found."),
            title="Support Table",
            border_style="red",
        )

    start = state.browser_offset
    stop = min(start + visible_count, browser_count)
    selected = feature.browser_blocks[state.selected_browser]

    labels: list[Text] = []
    for index in range(start, stop):
        block = feature.browser_blocks[index]
        tab_style = "bold white on blue" if index == state.selected_browser else "dim"
        labels.append(Text(f" {block.browser_name} ", style=tab_style))

    tabs_bar = Text()
    if start > 0:
        tabs_bar.append("< ", style="dim")
    tabs_bar.append_text(Text.assemble(*labels))
    if stop < browser_count:
        tabs_bar.append(" >", style="dim")

    range_count = len(selected.ranges)
    if range_count:
        state.range_scroll = max(0, min(state.range_scroll, range_count - 1))
    else:
        state.range_scroll = 0

    preview_size = max(max_rows - 5, 2)
    visible_ranges = selected.ranges[state.range_scroll : state.range_scroll + preview_size]

    rows: list[Text] = []
    for support_range in visible_ranges:
        rows.append(_format_support_line(support_range, include_usage=False))
    if range_count > state.range_scroll + preview_size:
        remaining = range_count - (state.range_scroll + preview_size)
        rows.append(Text(f"... {remaining} more", style="dim"))
    if not rows:
        rows = [Text("No range data", style="dim")]

    row_start = state.range_scroll + 1 if visible_ranges else 0
    row_end = state.range_scroll + len(visible_ranges) if visible_ranges else 0
    footer = Text(
        f"Browser {state.selected_browser + 1}/{browser_count} ({selected.browser_name})  "
        f"rows {row_start}-{row_end}"
        f" of {range_count}",
        style="dim",
    )
    return Panel(
        Group(tabs_bar, Text(""), *rows, Text(""), footer),
        title="Support Table",
        border_style="green",
    )


def _tab_panel(feature: FeatureFull, state: _TuiState, max_rows: int) -> Panel:
    sections = _tab_sections(feature)
    state.tab_index = max(0, min(state.tab_index, len(sections) - 1))
    tab_name, tab_lines = sections[state.tab_index]
    state.tab_scroll = max(0, min(state.tab_scroll, max(len(tab_lines) - 1, 0)))

    labels: list[Text] = []
    for idx, (name, _lines) in enumerate(sections):
        style = "bold white on blue" if idx == state.tab_index else "dim"
        labels.append(Text(f" {name} ", style=style))
    tabs_bar = Text.assemble(*labels)

    visible_count = max(max_rows - 4, 4)
    visible_lines = tab_lines[state.tab_scroll : state.tab_scroll + visible_count]
    payload = [_linkify_line(line) for line in visible_lines] or [Text("No content", style="dim")]
    payload.extend(
        [
            Text(""),
            Text(
                f"Tab {state.tab_index + 1}/{len(sections)} ({tab_name})  "
                f"rows {state.tab_scroll + 1}-{state.tab_scroll + len(visible_lines)}"
                f" of {len(tab_lines)}",
                style="dim",
            ),
            Text("Tab/[/] switch sections  PgUp/PgDn scroll section", style="dim"),
        ]
    )
    return Panel(
        Group(tabs_bar, Text(""), *payload),
        title="Feature Details",
        border_style="magenta",
    )


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
        body.append(_linkify_line(feature.spec_url, base_style="cyan"))
    body.extend([Text(""), usage_line, Text(""), Text(description)])
    return Panel(Group(*body), border_style="white")


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
        "←/→ select browser  ↑/↓ scroll browser  PgUp/PgDn page browsers + scroll section  "
        "Tab/[/] switch section  q/Esc quit",
        style="dim",
    )
    return Panel(Group(controls, legend), border_style="grey50")


def _normalize_state(state: _TuiState, feature: FeatureFull) -> None:
    browser_count = len(feature.browser_blocks)
    if browser_count == 0:
        state.selected_browser = 0
        state.browser_offset = 0
        state.range_scroll = 0
    else:
        state.selected_browser = max(0, min(state.selected_browser, browser_count - 1))
        max_range = max(len(feature.browser_blocks[state.selected_browser].ranges) - 1, 0)
        state.range_scroll = max(0, min(state.range_scroll, max_range))

    sections = _tab_sections(feature)
    state.tab_index = max(0, min(state.tab_index, len(sections) - 1))
    active_lines = sections[state.tab_index][1]
    state.tab_scroll = max(0, min(state.tab_scroll, max(len(active_lines) - 1, 0)))


def _move_browser(state: _TuiState, feature: FeatureFull, delta: int) -> None:
    if not feature.browser_blocks:
        return
    state.selected_browser = max(
        0, min(state.selected_browser + delta, len(feature.browser_blocks) - 1)
    )
    state.range_scroll = 0


def _scroll_browser_ranges(state: _TuiState, feature: FeatureFull, delta: int) -> None:
    if not feature.browser_blocks:
        return
    ranges = feature.browser_blocks[state.selected_browser].ranges
    max_range = max(len(ranges) - 1, 0)
    state.range_scroll = max(0, min(state.range_scroll + delta, max_range))


def _switch_tab(state: _TuiState, feature: FeatureFull, delta: int) -> None:
    sections = _tab_sections(feature)
    if not sections:
        return
    state.tab_index = (state.tab_index + delta) % len(sections)
    state.tab_scroll = 0


def _scroll_tab(state: _TuiState, feature: FeatureFull, delta: int) -> None:
    sections = _tab_sections(feature)
    active_lines = sections[state.tab_index][1]
    max_scroll = max(len(active_lines) - 1, 0)
    state.tab_scroll = max(0, min(state.tab_scroll + delta, max_scroll))


def _page_browsers(state: _TuiState, feature: FeatureFull, direction: int) -> None:
    if not feature.browser_blocks:
        return
    step = max(state.browser_visible_count, 1)
    _move_browser(state, feature, direction * step)


def _jump_home(state: _TuiState) -> None:
    state.range_scroll = 0
    state.tab_scroll = 0


def _jump_end(state: _TuiState, feature: FeatureFull) -> None:
    if feature.browser_blocks:
        selected = feature.browser_blocks[state.selected_browser]
        state.range_scroll = max(len(selected.ranges) - 1, 0)
    sections = _tab_sections(feature)
    active_lines = sections[state.tab_index][1]
    state.tab_scroll = max(len(active_lines) - 1, 0)


def _build_layout_for_size(
    feature: FeatureFull,
    state: _TuiState,
    width: int,
    height: int,
) -> Layout:
    _normalize_state(state, feature)

    root = Layout()
    footer_size = 4
    feature_size = 10 if height >= 32 else 8
    support_size = min(max(height // 3, 9), 16)
    details_size = max(height - footer_size - feature_size - support_size, 8)

    support_rows = max(support_size - 3, 5)
    details_rows = max(details_size - 2, 6)

    root.split_column(
        Layout(name="feature", size=feature_size),
        Layout(name="support", size=support_size),
        Layout(name="details", size=details_size),
        Layout(name="footer", size=footer_size),
    )

    root["feature"].update(_feature_heading_panel(feature, width))
    root["support"].update(_support_overview_panel(feature, state, width - 6, support_rows))
    root["details"].update(_tab_panel(feature, state, details_rows))
    root["footer"].update(_footer_panel())
    return root


def _build_layout(feature: FeatureFull, state: _TuiState, console: Console) -> Layout:
    return _build_layout_for_size(feature, state, console.size.width, console.size.height)


def _print_static(console: Console, feature: FeatureFull) -> None:
    lines = _render_lines(feature, console.size.width - 6)
    renderable = Panel(Text("\n".join(lines)), title=f"/{feature.slug}", border_style="blue")
    console.print(renderable)


def run_fullscreen(feature: FeatureFull) -> None:
    """Render full output with Textual in TTY mode and static Rich output otherwise."""
    console = Console()
    if sys.stdout.isatty():
        from .textual_fullscreen import run_textual_fullscreen

        run_textual_fullscreen(feature)
        return

    _print_static(console, feature)
