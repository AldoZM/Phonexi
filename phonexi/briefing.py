"""Optional prior-context file (-c/--context) loaded before the hotkeys start.

Gives the model background — the job posting, the stack, your own experience —
so answers arrive oriented instead of cold.
"""

from pathlib import Path

# Keeps a runaway file from eating the context window and inflating every call.
MAX_CHARS = 20_000

ALLOWED_SUFFIXES = (".md", ".txt")


class BriefingError(Exception):
    """The context file is unusable; Phonexi aborts instead of starting blind."""


def load(path) -> str:
    path = Path(path)

    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise BriefingError(
            f"{path}: unsupported format '{path.suffix or '(none)'}' - use .md or .txt"
        )

    if not path.exists():
        raise BriefingError(f"{path}: file not found")

    if not path.is_file():
        raise BriefingError(f"{path}: not a file")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise BriefingError(f"{path}: not valid UTF-8 text") from None

    text = text.strip()

    if not text:
        raise BriefingError(f"{path}: file is empty")

    if len(text) > MAX_CHARS:
        raise BriefingError(
            f"{path}: too large - {len(text)} characters, limit is {MAX_CHARS}"
        )

    return text
