"""Interactive search-result selection UI."""

from __future__ import annotations

from collections.abc import Iterable
import sys

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from ..model import SearchMatch
from ..util.text import ellipsize


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

    console = Console()
    console.print(Text("Select a feature", style="bold cyan"))
    width = max(console.size.width, 40)
    for idx, item in enumerate(options, start=1):
        slug_piece = f"/{item.slug}"
        text_width = max(width - len(slug_piece) - 10, 10)
        label = ellipsize(item.title, text_width)
        console.print(Text(f"{idx:>2}. {label}  {slug_piece}"))

    while True:
        choice = console.input("[dim]Enter number (or q to cancel): [/]").strip().lower()
        if choice in {"q", "quit", "esc"}:
            return None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1].slug
        console.print("Invalid selection. Try again.", style="yellow")
