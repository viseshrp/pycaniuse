"""Feature selection helpers for ambiguous search results."""

from __future__ import annotations

import sys

from ..model import SearchMatch
from .textual_select import run_textual_select


def _supports_interactive_selection() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def select_match(matches: list[SearchMatch]) -> str | None:
    """Choose a slug from search matches.

    Behavior:
    - No matches: return None.
    - Single match: return that slug.
    - Interactive TTY: run Textual selector.
    - Non-interactive: return first slug.
    """
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0].slug
    if _supports_interactive_selection():
        return run_textual_select(matches)
    return matches[0].slug
