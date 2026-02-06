"""Full-screen interactive UI for --full mode."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
import select
import sys
import termios
import tty

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ..constants import STATUS_ICON_MAP, STATUS_LABEL_MAP
from ..model import FeatureFull
from ..util.text import wrap_lines


@contextmanager
def _raw_mode(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _read_key(timeout: float = 0.2) -> str | None:
    if os.name == "nt":  # pragma: no cover
        import msvcrt

        if not msvcrt.kbhit():  # type: ignore[attr-defined]
            return None
        key: str = msvcrt.getwch()  # type: ignore[attr-defined]
        if key in {"\x00", "\xe0"}:
            second: str = msvcrt.getwch()  # type: ignore[attr-defined]
            return {
                "H": "up",
                "P": "down",
                "K": "left",
                "M": "right",
                "I": "pgup",
                "Q": "pgdn",
                "G": "home",
                "O": "end",
            }.get(second)
        if key in {"\n", "\r"}:
            return "enter"
        if key == "\x1b":
            return "esc"
        if key.lower() == "q":
            return "q"
        if key.isdigit():
            return key
        return None

    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    first = sys.stdin.read(1)
    if first in {"q", "Q"}:
        return "q"
    if first.isdigit():
        return first
    if first in {"\n", "\r"}:
        return "enter"
    if first != "\x1b":
        return None

    if not select.select([sys.stdin], [], [], 0.01)[0]:
        return "esc"
    second = sys.stdin.read(1)
    if second != "[":
        return "esc"
    if not select.select([sys.stdin], [], [], 0.01)[0]:
        return "esc"
    third = sys.stdin.read(1)

    mapping = {
        "A": "up",
        "B": "down",
        "C": "right",
        "D": "left",
        "H": "home",
        "F": "end",
    }
    if third in mapping:
        return mapping[third]

    if third in {"5", "6"} and select.select([sys.stdin], [], [], 0.01)[0]:
        fourth = sys.stdin.read(1)
        if fourth == "~":
            return "pgup" if third == "5" else "pgdn"

    return None


def _support_lines(feature: FeatureFull) -> list[str]:
    lines: list[str] = []
    for block in feature.browser_blocks:
        lines.append(block.browser_name)
        for support_range in block.ranges:
            icon = STATUS_ICON_MAP.get(support_range.status, STATUS_ICON_MAP["u"])
            label = STATUS_LABEL_MAP.get(support_range.status, STATUS_LABEL_MAP["u"])
            lines.append(f"  {support_range.range_text}: {icon} {label}")
        lines.append("")
    return lines or ["No browser support blocks found."]


def run_fullscreen(feature: FeatureFull) -> None:
    """Run the full-screen keyboard-first Rich UI."""
    tabs = list(feature.tabs.keys())
    if not tabs:
        tabs = ["Info"]
        feature_tabs = {"Info": "No additional sections available."}
    else:
        feature_tabs = feature.tabs

    selected_tab_idx = 0
    if "Notes" in tabs:
        selected_tab_idx = tabs.index("Notes")

    scroll_offset = 0
    support_scroll_offset = 0

    console = Console()

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        # Fallback for non-interactive environments.
        console.print(Panel(Text(feature.title, style="bold"), title=f"/{feature.slug}"))
        for line in _support_lines(feature):
            console.print(line)
        for tab_name in tabs:
            console.print(f"\n[{tab_name}]\n{feature_tabs.get(tab_name, '')}")
        return

    with (
        _raw_mode(enabled=(os.name != "nt")),
        Live(console=console, screen=True, refresh_per_second=20) as live,
    ):
        while True:
            width = console.size.width
            height = console.size.height

            if width < 60 or height < 20:
                warning = Panel(
                    Text("Terminal too small; resize", style="bold yellow"),
                    title="pycaniuse",
                    border_style="yellow",
                )
                live.update(warning)
                key = _read_key()
                if key in {"q", "esc"}:
                    return
                continue

            current_tab = tabs[selected_tab_idx]
            tab_content = feature_tabs.get(current_tab, "")
            content_lines = wrap_lines(tab_content, width - 6)
            support_lines = wrap_lines("\n".join(_support_lines(feature)), width - 6)

            max_support = max(len(support_lines) - 8, 0)
            support_scroll_offset = max(0, min(support_scroll_offset, max_support))

            content_window = max(height - 20, 3)
            max_scroll = max(len(content_lines) - content_window, 0)
            scroll_offset = max(0, min(scroll_offset, max_scroll))

            header_lines = [Text(feature.title, style="bold")]
            if feature.spec_url:
                suffix = f" [{feature.spec_status}]" if feature.spec_status else ""
                header_lines.append(Text(f"Spec: {feature.spec_url}{suffix}"))
            usage_parts: list[str] = []
            if feature.usage_supported is not None:
                usage_parts.append(f"✅ {feature.usage_supported:.2f}%")
            if feature.usage_partial is not None:
                usage_parts.append(f"◐ {feature.usage_partial:.2f}%")
            if feature.usage_total is not None:
                usage_parts.append(f"Total {feature.usage_total:.2f}%")
            if usage_parts:
                header_lines.append(Text("Usage: " + "  ".join(usage_parts)))

            tab_row = []
            for idx, tab_name in enumerate(tabs, start=1):
                style = "reverse bold" if idx - 1 == selected_tab_idx else "dim"
                tab_row.append(Text(f" {idx}:{tab_name} ", style=style))
            tabs_text = Text.assemble(*tab_row)

            group = Group(
                Panel(Group(*header_lines), border_style="blue", title=f"/{feature.slug}"),
                Panel(
                    Text(
                        "\n".join(support_lines[support_scroll_offset : support_scroll_offset + 8])
                    ),
                    title="Support",
                    border_style="cyan",
                ),
                Panel(tabs_text, border_style="magenta", title="Tabs"),
                Panel(
                    Text("\n".join(content_lines[scroll_offset : scroll_offset + content_window])),
                    title=current_tab,
                    border_style="green",
                ),
                Text("←/→ tabs  1-9 jump  ↑/↓ scroll  PgUp/PgDn/Home/End  q/Esc quit", style="dim"),
            )
            live.update(group)

            key = _read_key()
            if key is None:
                continue
            if key in {"q", "esc"}:
                return
            if key == "left":
                selected_tab_idx = max(0, selected_tab_idx - 1)
                scroll_offset = 0
            elif key == "right":
                selected_tab_idx = min(len(tabs) - 1, selected_tab_idx + 1)
                scroll_offset = 0
            elif key and key.isdigit() and key != "0":
                idx = int(key) - 1
                if idx < len(tabs):
                    selected_tab_idx = idx
                    scroll_offset = 0
            elif key == "up":
                scroll_offset = max(0, scroll_offset - 1)
            elif key == "down":
                scroll_offset = min(max_scroll, scroll_offset + 1)
            elif key == "pgup":
                scroll_offset = max(0, scroll_offset - max(3, content_window // 2))
            elif key == "pgdn":
                scroll_offset = min(max_scroll, scroll_offset + max(3, content_window // 2))
            elif key == "home":
                scroll_offset = 0
            elif key == "end":
                scroll_offset = max_scroll
