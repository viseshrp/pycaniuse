"""Full-screen interactive UI for --full mode."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
import select
import sys
import termios
import textwrap
import tty

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ..constants import STATUS_ICON_MAP, STATUS_LABEL_MAP
from ..model import FeatureFull
from ..util.text import extract_note_markers


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

    lines.append("Legend")
    lines.append(f"- {STATUS_ICON_MAP['y']} = {STATUS_LABEL_MAP['y']}")
    lines.append(f"- {STATUS_ICON_MAP['n']} = {STATUS_LABEL_MAP['n']}")
    lines.append(f"- {STATUS_ICON_MAP['a']} = {STATUS_LABEL_MAP['a']}")
    lines.append(f"- {STATUS_ICON_MAP['u']} = {STATUS_LABEL_MAP['u']}")

    return lines


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


def run_fullscreen(feature: FeatureFull) -> None:
    """Render a full feature page; in TTY use a pager for stable navigation."""
    console = Console()
    lines = _render_lines(feature, console.size.width - 6)
    renderable = Panel(Text("\n".join(lines)), title=f"/{feature.slug}", border_style="blue")
    interactive_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if interactive_tty and hasattr(console, "pager"):
        with console.pager(styles=True):
            console.print(renderable)
        return
    console.print(renderable)
