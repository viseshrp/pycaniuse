"""Interactive search-result selection UI."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
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

from ..model import SearchMatch
from ..util.text import ellipsize


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
        first: str = msvcrt.getwch()  # type: ignore[attr-defined]
        if first in {"\x00", "\xe0"}:
            second: str = msvcrt.getwch()  # type: ignore[attr-defined]
            return {"H": "up", "P": "down"}.get(second)
        if first in {"\r", "\n"}:
            return "enter"
        if first == "\x1b":
            return "esc"
        if first.lower() == "q":
            return "q"
        return None

    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    first = sys.stdin.read(1)
    if first in {"\n", "\r"}:
        return "enter"
    if first in {"q", "Q"}:
        return "q"
    if first == "\x1b":
        if select.select([sys.stdin], [], [], 0.01)[0]:
            second = sys.stdin.read(1)
            if second == "[" and select.select([sys.stdin], [], [], 0.01)[0]:
                third = sys.stdin.read(1)
                return {"A": "up", "B": "down"}.get(third, "esc")
        return "esc"
    return None


def _build_frame(
    matches: list[SearchMatch], selected_idx: int, width: int, start: int, stop: int
) -> Panel:
    rows: list[Text] = []
    for index in range(start, stop):
        item = matches[index]
        prefix = ">" if index == selected_idx else "*"
        slug_piece = f"/{item.slug}"
        text_width = max(width - len(slug_piece) - 8, 10)
        label = ellipsize(item.title, text_width)
        style = "bold white" if index == selected_idx else "white"
        rows.append(Text(f"{prefix} {label}  {slug_piece}", style=style))

    footer = Text("↑/↓ move  Enter select  q/Esc cancel", style="dim")
    group = Group(*rows, Text(""), footer)
    return Panel(group, title="Select a feature", border_style="cyan")


def select_match(matches: Iterable[SearchMatch]) -> str | None:
    """Return the selected slug or None when user cancels."""
    options = list(matches)
    if not options:
        return None
    if len(options) == 1:
        return options[0].slug

    # Non-interactive environments cannot support key loops; choose first deterministically.
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return options[0].slug

    selected = 0
    top = 0
    console = Console()

    with (
        _raw_mode(enabled=(os.name != "nt")),
        Live(console=console, refresh_per_second=20, transient=True) as live,
    ):
        while True:
            height = max(console.size.height - 6, 5)
            if selected < top:
                top = selected
            if selected >= top + height:
                top = selected - height + 1
            stop = min(len(options), top + height)
            live.update(_build_frame(options, selected, console.size.width, top, stop))

            key = _read_key()
            if key is None:
                continue
            if key == "up":
                selected = max(0, selected - 1)
            elif key == "down":
                selected = min(len(options) - 1, selected + 1)
            elif key == "enter":
                return options[selected].slug
            elif key in {"q", "esc"}:
                return None
