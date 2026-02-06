"""Text utility helpers."""

from __future__ import annotations

import re
import textwrap

_WHITESPACE_RE = re.compile(r"\s+")
_NOTE_RE = re.compile(r"^#(\d+)$")


def normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace and trim ends."""
    return _WHITESPACE_RE.sub(" ", value).strip()


def parse_percent(value: str | None) -> float | None:
    """Parse a percent string into float (supports comma decimal)."""
    if not value:
        return None
    cleaned = normalize_whitespace(value).replace("%", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def wrap_lines(value: str, width: int) -> list[str]:
    """Wrap text to a specific width while preserving paragraph breaks."""
    width = max(width, 20)
    paragraphs = [p for p in value.splitlines()]
    wrapped: list[str] = []
    for paragraph in paragraphs:
        if not paragraph.strip():
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(paragraph, width=width) or [""])
    return wrapped


def ellipsize(value: str, width: int) -> str:
    """Shorten long strings while preserving suffix visibility."""
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    if width <= 1:
        return "…"
    return f"{value[: width - 1]}…"


def extract_note_markers(raw_classes: tuple[str, ...]) -> list[str]:
    """Extract note marker tokens like #1, #4 from class lists."""
    return [match.group(1) for token in raw_classes if (match := _NOTE_RE.match(token))]
