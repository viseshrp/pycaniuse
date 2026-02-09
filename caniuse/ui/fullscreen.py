"""Full-screen interactive UI for --full mode."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import re
import select
import sys
import textwrap
from typing import Any, Literal, cast

from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ..constants import STATUS_ICON_MAP, STATUS_LABEL_MAP
from ..model import BrowserSupportBlock, FeatureFull, SupportRange
from ..util.text import extract_note_markers

_CARD_WIDTH = 24
_KEY = Literal[
    "up",
    "down",
    "left",
    "right",
    "pageup",
    "pagedown",
    "home",
    "end",
    "tab",
    "shift_tab",
    "next_tab",
    "prev_tab",
    "quit",
    "noop",
]
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


@dataclass
class _TuiState:
    selected_browser: int = 0
    browser_offset: int = 0
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

    if feature.notes_text:
        lines.append("Notes")
        lines.append(feature.notes_text)
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
    visible_count = max(width // _CARD_WIDTH, 1)
    _fit_browser_window(state, browser_count, visible_count)
    if browser_count == 0:
        return Panel(
            Text("No browser support blocks found."),
            title="Support Table",
            border_style="red",
        )

    start = state.browser_offset
    stop = min(start + visible_count, browser_count)
    cards: list[Panel] = []
    for index in range(start, stop):
        block = feature.browser_blocks[index]
        is_selected = index == state.selected_browser
        preview_size = max(max_rows - 2, 2) if is_selected else max(max_rows - 4, 2)
        content: list[Text] = []
        for support_range in block.ranges[:preview_size]:
            content.append(_format_support_line(support_range, include_usage=False))
        if len(block.ranges) > preview_size:
            content.append(Text(f"... {len(block.ranges) - preview_size} more", style="dim"))
        if not content:
            content = [Text("No range data", style="dim")]
        cards.append(
            Panel(
                Group(*content),
                title=block.browser_name,
                border_style="bright_cyan" if is_selected else "grey50",
            )
        )

    footer = Text(f"Showing browsers {start + 1}-{stop} of {browser_count}", style="dim")
    return Panel(
        Group(
            Columns(cards, equal=True, expand=True),
            Text(""),
            footer,
        ),
        title="Support Table",
        border_style="green",
    )


def _selected_browser(feature: FeatureFull, state: _TuiState) -> BrowserSupportBlock | None:
    if not feature.browser_blocks:
        return None
    idx = max(0, min(state.selected_browser, len(feature.browser_blocks) - 1))
    return feature.browser_blocks[idx]


def _support_detail_panel(feature: FeatureFull, state: _TuiState, max_rows: int) -> Panel:
    selected = _selected_browser(feature, state)
    if selected is None:
        return Panel(Text("No browser selected."), title="Browser Details", border_style="red")
    range_count = len(selected.ranges)
    if range_count == 0:
        return Panel(Text("No support ranges."), title=selected.browser_name, border_style="cyan")

    state.range_scroll = max(0, min(state.range_scroll, range_count - 1))
    visible_count = max(max_rows - 3, 4)
    visible = selected.ranges[state.range_scroll : state.range_scroll + visible_count]

    rows: list[Text] = []
    for support_range in visible:
        rows.append(_format_support_line(support_range, include_usage=True))

    position = f"Rows {state.range_scroll + 1}-{state.range_scroll + len(visible)} of {range_count}"
    rows.extend(
        [
            Text(""),
            Text(position, style="dim"),
            Text("↑/↓ scroll selected browser ranges", style="dim"),
        ]
    )
    return Panel(Group(*rows), title=f"{selected.browser_name} Support", border_style="cyan")


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
    payload = [Text(line) for line in visible_lines] or [Text("No content", style="dim")]
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
        body.append(Text(feature.spec_url, style="cyan"))
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
        "←/→ select browser  ↑/↓ scroll browser  Tab/[/] switch section  "
        "PgUp/PgDn scroll section  q/Esc quit",
        style="dim",
    )
    return Panel(Group(controls, legend), border_style="grey50")


def _build_layout(feature: FeatureFull, state: _TuiState, console: Console) -> Layout:
    size = console.size
    root = Layout()
    footer_size = 4
    feature_size = 10 if size.height >= 32 else 8
    support_size = min(max(size.height // 3, 9), 16)
    details_size = max(size.height - footer_size - feature_size - support_size, 8)

    support_rows = max(support_size - 3, 5)
    details_rows = max(details_size - 2, 6)

    root.split_column(
        Layout(name="feature", size=feature_size),
        Layout(name="support", size=support_size),
        Layout(name="details", size=details_size),
        Layout(name="footer", size=footer_size),
    )
    root["details"].split_row(
        Layout(name="browser"),
        Layout(name="tabs"),
    )

    root["feature"].update(_feature_heading_panel(feature, size.width))
    root["support"].update(_support_overview_panel(feature, state, size.width - 6, support_rows))
    root["browser"].update(_support_detail_panel(feature, state, details_rows))
    root["tabs"].update(_tab_panel(feature, state, details_rows))
    root["footer"].update(_footer_panel())
    return root


def _decode_escape_sequence(sequence: bytes) -> _KEY:
    mapping: dict[bytes, _KEY] = {
        b"[A": "up",
        b"[B": "down",
        b"[C": "right",
        b"[D": "left",
        b"[5~": "pageup",
        b"[6~": "pagedown",
        b"[H": "home",
        b"[F": "end",
        b"[Z": "shift_tab",
    }
    return mapping.get(sequence, "quit")


def _read_key_posix(fd: int) -> _KEY:
    data = os.read(fd, 1)
    if not data:
        return "noop"

    char = data.decode(errors="ignore")
    if char in {"q", "Q"}:
        return "quit"
    if char == "\t":
        return "tab"
    if char in {"\r", "\n"}:
        return "noop"
    if char in {"[", "]"}:
        return "prev_tab" if char == "[" else "next_tab"
    if char in {"\x1b"}:
        sequence = b""
        while select.select([fd], [], [], 0.01)[0]:
            sequence += os.read(fd, 1)
            if sequence.endswith((b"A", b"B", b"C", b"D", b"~", b"Z", b"H", b"F")):
                break
        return _decode_escape_sequence(sequence)
    if char.lower() == "h":
        return "left"
    if char.lower() == "j":
        return "down"
    if char.lower() == "k":
        return "up"
    if char.lower() == "l":
        return "right"
    return "noop"


def _read_key_windows() -> _KEY:
    import msvcrt  # pragma: no cover

    getwch = cast(Callable[[], str] | None, getattr(msvcrt, "getwch", None))
    if getwch is None:
        return "noop"

    char = getwch()
    if char in {"q", "Q", "\x1b"}:
        return "quit"
    if char == "\t":
        return "tab"
    if char == "[":
        return "prev_tab"
    if char == "]":
        return "next_tab"
    if char in {"h", "H"}:
        return "left"
    if char in {"j", "J"}:
        return "down"
    if char in {"k", "K"}:
        return "up"
    if char in {"l", "L"}:
        return "right"

    if char in {"\x00", "\xe0"}:
        special = getwch()
        mapping: dict[str, _KEY] = {
            "H": "up",
            "P": "down",
            "K": "left",
            "M": "right",
            "I": "pageup",
            "Q": "pagedown",
            "G": "home",
            "O": "end",
        }
        return mapping.get(special, "noop")
    return "noop"


class _RawInput:
    def __init__(self) -> None:
        self._fd: int | None = None
        self._old_settings: Any = None

    def __enter__(self) -> _RawInput:
        if os.name == "nt":
            return self
        import termios
        import tty

        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object | None,
    ) -> None:
        if os.name == "nt":
            return
        if self._fd is None or self._old_settings is None:
            return
        import termios

        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)

    def read_key(self) -> _KEY:
        if os.name == "nt":
            return _read_key_windows()
        if self._fd is None:
            return "noop"
        return _read_key_posix(self._fd)


def _supports_tui(console: Console) -> bool:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    if not hasattr(console, "screen"):
        return False
    if not hasattr(sys.stdin, "fileno") or not hasattr(sys.stdin, "read"):
        return False
    try:
        sys.stdin.fileno()
    except (OSError, ValueError):
        return False
    return True


def _apply_key(key: _KEY, state: _TuiState, feature: FeatureFull) -> bool:
    browser_count = len(feature.browser_blocks)
    if key == "quit":
        return False
    if key in {"left"} and browser_count:
        state.selected_browser = max(0, state.selected_browser - 1)
        state.range_scroll = 0
    elif key in {"right"} and browser_count:
        state.selected_browser = min(browser_count - 1, state.selected_browser + 1)
        state.range_scroll = 0
    elif key in {"up"} and browser_count:
        state.range_scroll = max(state.range_scroll - 1, 0)
    elif key in {"down"} and browser_count:
        selected = feature.browser_blocks[state.selected_browser]
        state.range_scroll = min(state.range_scroll + 1, max(len(selected.ranges) - 1, 0))
    elif key in {"tab", "next_tab"}:
        section_count = len(_tab_sections(feature))
        state.tab_index = (state.tab_index + 1) % section_count
        state.tab_scroll = 0
    elif key in {"shift_tab", "prev_tab"}:
        section_count = len(_tab_sections(feature))
        state.tab_index = (state.tab_index - 1) % section_count
        state.tab_scroll = 0
    elif key == "pageup":
        state.tab_scroll = max(state.tab_scroll - 5, 0)
    elif key == "pagedown":
        active_lines = _tab_sections(feature)[state.tab_index][1]
        state.tab_scroll = min(state.tab_scroll + 5, max(len(active_lines) - 1, 0))
    elif key == "home":
        state.range_scroll = 0
        state.tab_scroll = 0
    elif key == "end":
        if browser_count:
            selected = feature.browser_blocks[state.selected_browser]
            state.range_scroll = max(len(selected.ranges) - 1, 0)
        active_lines = _tab_sections(feature)[state.tab_index][1]
        state.tab_scroll = max(len(active_lines) - 1, 0)
    return True


def _run_tui(console: Console, feature: FeatureFull) -> None:
    state = _TuiState()
    with (
        _RawInput() as raw,
        console.screen(hide_cursor=True),
        Live(
            _build_layout(feature, state, console),
            console=console,
            auto_refresh=False,
            screen=True,
        ) as live,
    ):
        while True:
            live.update(_build_layout(feature, state, console), refresh=True)
            key = raw.read_key()
            if not _apply_key(key, state, feature):
                break


def run_fullscreen(feature: FeatureFull) -> None:
    """Render full mode as interactive TUI when supported; otherwise print static output."""
    console = Console()
    if _supports_tui(console):
        _run_tui(console, feature)
        return

    lines = _render_lines(feature, console.size.width - 6)
    renderable = Panel(Text("\n".join(lines)), title=f"/{feature.slug}", border_style="blue")
    console.print(renderable)
