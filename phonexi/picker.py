"""Arrow-key model picker for -model, drawn in place with ANSI codes."""

import sys
from typing import Callable, TextIO

from phonexi.providers import Model

UP, DOWN = "H", "P"
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


def _rows(models: list[Model], cursor: int) -> list[str]:
    width = max(len(m.name) for m in models)
    return [
        f"{'>' if i == cursor else ' '} {m.provider:<7} {m.name:<{width}}  {m.capabilities}"
        for i, m in enumerate(models)
    ]


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
            f"-{what} needs an interactive terminal; run Phonexi from a console."
        )
    if not models:
        raise PickerUnavailableError(
            "No API key found — add GROQ_API_KEY or GEMINI_API_KEY to .env."
        )
    if read_key is None:
        import msvcrt
        read_key = msvcrt.getwch
        _enable_ansi()

    cursor = min(max(start, 0), len(models) - 1)
    out.write("Choose a model (Up/Down, Enter to confirm, Esc to cancel):\n")
    _draw(out, models, cursor, redraw=False)
    while True:
        key = read_key()
        if key in ENTER:
            return models[cursor]
        if key in CANCEL:
            return None
        if key in PREFIXES:
            arrow = read_key()
            if arrow == UP:
                cursor = max(cursor - 1, 0)
            elif arrow == DOWN:
                cursor = min(cursor + 1, len(models) - 1)
            else:
                continue
            _draw(out, models, cursor, redraw=True)
