"""Arrow-key model picker for -model, drawn in place with ANSI codes."""

import sys
from dataclasses import replace
from typing import Callable, TextIO

from phonexi.providers import Model

UP, DOWN, LEFT, RIGHT = "H", "P", "K", "M"
PREFIXES = ("\x00", "\xe0")  # msvcrt sends arrows as a prefix plus a letter
ENTER = ("\r", "\n")
CANCEL = ("\x1b", "\x03")  # Esc, Ctrl+C


class PickerUnavailableError(Exception):
    pass


def _enable_ansi() -> None:
    """Windows consoles ignore escape codes until VT processing is switched on."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except (AttributeError, OSError):
        pass


def _levels(row) -> tuple:
    # -model rows have no levels; -cli rows may.
    return getattr(row, "levels", ())


def _tail(row) -> str:
    return f"< {row.level} >" if _levels(row) else row.capabilities


def _rows(models: list, cursor: int) -> list[str]:
    width = max(len(m.name) for m in models)
    return [
        f"{'>' if i == cursor else ' '} {m.provider:<7} {m.name:<{width}}  {_tail(m)}"
        for i, m in enumerate(models)
    ]


def _step_level(row, step: int):
    """The row with its level moved one step, stopping at both ends."""
    levels = _levels(row)
    i = min(max(levels.index(row.level) + step, 0), len(levels) - 1)
    return replace(row, level=levels[i])


def _draw(out: TextIO, models: list[Model], cursor: int, redraw: bool) -> None:
    if redraw:
        out.write(f"\x1b[{len(models)}A")
    for row in _rows(models, cursor):
        out.write(f"\x1b[2K{row}\n")
    out.flush()


def choose(
    models: list[Model],
    start: int = 0,
    read_key: "Callable[[], str] | None" = None,
    out: "TextIO | None" = None,
    is_tty: "bool | None" = None,
    what: str = "model",
) -> "Model | None":
    """Let the user pick a model. Returns None when cancelled."""
    out = out or sys.stdout
    if is_tty is None:
        is_tty = sys.stdin.isatty() and out.isatty()
    if not is_tty:
        raise PickerUnavailableError(
            f"-{what.lower()} needs an interactive terminal; run Phonexi from a console."
        )
    if not models:
        raise PickerUnavailableError(
            "No API key found — add GROQ_API_KEY or GEMINI_API_KEY to .env."
        )
    if read_key is None:
        import msvcrt
        read_key = msvcrt.getwch
        _enable_ansi()

    # A copy: Left/Right replaces rows with their new level, and the caller's
    # list must not change under it.
    rows = list(models)
    cursor = min(max(start, 0), len(rows) - 1)
    keys = "Up/Down, Left/Right effort" if any(_levels(r) for r in rows) else "Up/Down"
    out.write(f"Choose a {what} ({keys}, Enter to confirm, Esc to cancel):\n")
    _draw(out, rows, cursor, redraw=False)
    while True:
        key = read_key()
        if key in ENTER:
            return rows[cursor]
        if key in CANCEL:
            return None
        if key in PREFIXES:
            arrow = read_key()
            if arrow == UP:
                cursor = max(cursor - 1, 0)
            elif arrow == DOWN:
                cursor = min(cursor + 1, len(rows) - 1)
            elif arrow in (LEFT, RIGHT) and _levels(rows[cursor]):
                rows[cursor] = _step_level(rows[cursor], -1 if arrow == LEFT else 1)
            else:
                continue
            _draw(out, rows, cursor, redraw=True)
