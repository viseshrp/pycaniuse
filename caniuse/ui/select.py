"""Feature selection helpers for ambiguous search results."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from ..model import SearchMatch


def _supports_interactive_selection() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _render_choices(console: Console, matches: list[SearchMatch]) -> None:
    table = Table(title="Select a feature", show_header=True)
    table.add_column("#", style="cyan", justify="right", width=4)
    table.add_column("Feature", style="bold")
    table.add_column("Slug", style="dim")

    for index, match in enumerate(matches, start=1):
        table.add_row(str(index), match.title, f"/{match.slug}")

    console.print(table)
    console.print("Use number to select, or q to cancel.", style="dim")


def _prompt_for_match(console: Console, matches: list[SearchMatch]) -> str | None:
    choices = {str(idx) for idx in range(1, len(matches) + 1)}
    while True:
        selected = Prompt.ask("Selection", default="1").strip()
        if selected.lower() in {"q", "quit", "exit"}:
            return None
        if selected in choices:
            return matches[int(selected) - 1].slug
        console.print("Invalid selection. Enter a listed number, or q to cancel.", style="yellow")


def select_match(matches: list[SearchMatch]) -> str | None:
    """Choose a slug from search matches.

    Behavior:
    - No matches: return None.
    - Single match: return that slug.
    - Interactive TTY: run Rich selector.
    - Non-interactive: return first slug.
    """
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0].slug
    if _supports_interactive_selection():
        console = Console()
        _render_choices(console, matches)
        return _prompt_for_match(console, matches)
    return matches[0].slug
