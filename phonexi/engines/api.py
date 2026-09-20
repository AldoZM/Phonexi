"""The default engine: the Groq/Gemini API that processor.py already speaks.

A thin adapter, not a move. processor.py stays where it is; this only gives it
the Engine shape and turns its errors into provider-neutral ones so the
listener catches the same two exceptions whoever answers.
"""

from pathlib import Path
from typing import Iterator

from phonexi.engines.base import EngineError, EngineNotConfiguredError
from phonexi.processor import (
    Context,
    GroqAPIError,
    GroqNotConfiguredError,
    process,
    process_text,
)


class ApiEngine:
    LABEL = "API"

    def answer_image(self, path: Path, briefing: "str | None" = None) -> Iterator[str]:
        yield from _translate(lambda: process(path, briefing=briefing))

    def answer_text(
        self,
        question: str,
        context: "Context | None" = None,
        briefing: "str | None" = None,
    ) -> Iterator[str]:
        yield from _translate(
            lambda: process_text(question, context=context, briefing=briefing)
        )


def _translate(make_stream) -> Iterator[str]:
    """Re-raise processor's Groq-named errors under the neutral names.

    The stream is built inside the try as well: a missing key raises when the
    client is created, which is before the first token.
    """
    try:
        yield from make_stream()
    except GroqNotConfiguredError as exc:
        raise EngineNotConfiguredError(
            f"{exc.key_name} not set — add it to .env"
        ) from exc
    except GroqAPIError as exc:
        raise EngineError(str(exc)) from exc
