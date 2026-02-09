"""Interactive search-result selection UI."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import os
import select
import sys
from typing import Any, Literal, cast

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ..model import SearchMatch
from ..util.text import ellipsize

_KEY = Literal["up", "down", "enter", "quit", "noop"]


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


def _visible_window(selected_idx: int, total: int, height: int) -> tuple[int, int]:
    visible = max(height - 6, 1)
    if total <= visible:
        return 0, total
    start = selected_idx - (visible // 2)
    start = max(start, 0)
    start = min(start, total - visible)
    return start, min(start + visible, total)


def _decode_escape_sequence(sequence: bytes) -> _KEY:
    normalized = sequence.replace(b"O", b"[")
    if normalized.endswith(b"A"):
        return "up"
    if normalized.endswith(b"B"):
        return "down"
    return "noop"


def _read_key_posix(fd: int) -> _KEY:
    data = os.read(fd, 1)
    if not data:
        return "noop"

    char = data.decode(errors="ignore")
    if char in {"q", "Q"}:
        return "quit"
    if char in {"\r", "\n"}:
        return "enter"
    if char in {"\x1b"}:
        sequence = b""
        while select.select([fd], [], [], 0.01)[0]:
            sequence += os.read(fd, 1)
            if sequence.endswith((b"A", b"B")):
                break
        if not sequence:
            return "quit"
        return _decode_escape_sequence(sequence)
    if char.lower() == "k":
        return "up"
    if char.lower() == "j":
        return "down"
    return "noop"


def _read_key_windows() -> _KEY:
    import msvcrt  # pragma: no cover

    getwch = cast(Callable[[], str] | None, getattr(msvcrt, "getwch", None))
    if getwch is None:
        return "noop"

    char = getwch()
    if char in {"q", "Q", "\x1b"}:
        return "quit"
    if char in {"\r", "\n"}:
        return "enter"
    if char in {"k", "K"}:
        return "up"
    if char in {"j", "J"}:
        return "down"
    if char in {"\x00", "\xe0"}:
        special = getwch()
        mapping: dict[str, _KEY] = {
            "H": "up",
            "P": "down",
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


def _supports_key_loop(console: Console) -> bool:
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


def _select_match_by_number(console: Console, options: list[SearchMatch]) -> str | None:
    while True:
        selected = console.input("[dim]Enter number (or q to cancel): [/]").strip().lower()
        if selected in {"q", "quit", "esc"}:
            return None
        if selected.isdigit():
            idx = int(selected)
            if 1 <= idx <= len(options):
                return options[idx - 1].slug
        console.print("Invalid selection. Try again.", style="yellow")


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
    width = max(console.size.width, 40)
    if not _supports_key_loop(console):
        console.print(
            _build_frame(
                options,
                selected_idx=0,
                width=width,
                start=0,
                stop=len(options),
            )
        )
        return _select_match_by_number(console, options)

    selected_idx = 0
    with (
        _RawInput() as raw,
        console.screen(hide_cursor=True),
        Live(
            _build_frame(
                options, selected_idx=selected_idx, width=width, start=0, stop=len(options)
            ),
            console=console,
            auto_refresh=False,
            screen=True,
        ) as live,
    ):
        while True:
            start, stop = _visible_window(selected_idx, len(options), console.size.height)
            live.update(
                _build_frame(
                    options,
                    selected_idx=selected_idx,
                    width=max(console.size.width, 40),
                    start=start,
                    stop=stop,
                ),
                refresh=True,
            )
            key = raw.read_key()
            if key == "up":
                selected_idx = max(0, selected_idx - 1)
            elif key == "down":
                selected_idx = min(len(options) - 1, selected_idx + 1)
            elif key == "enter":
                return options[selected_idx].slug
            elif key == "quit":
                return None
