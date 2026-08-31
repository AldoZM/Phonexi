import base64
from pathlib import Path
from typing import Iterator

from groq import Groq

from phonexi.config import (
    GROQ_API_KEY,
    GROQ_MODEL_TEXT,
    GROQ_MODEL_VISION,
    PROMPT,
)


class GroqNotConfiguredError(Exception):
    pass


class GroqAPIError(Exception):
    pass


BRIEFING_HEADER = (
    "Background about the candidate (stack, role, experience). Treat it as your own "
    "knowledge and answer straight from it. It is NOT the question, so never answer "
    "it directly. Never mention, quote, or allude to this background as a source: no "
    "'based on the context', no 'according to your document', no 'as you mentioned'. "
    "The reply is spoken aloud in an interview — it must sound like the candidate "
    "recalling their own work, and it must open with the answer itself:\n"
)


def _briefing_message(briefing: "str | None") -> "dict | None":
    if not briefing or not briefing.strip():
        return None
    return {"role": "system", "content": BRIEFING_HEADER + briefing.strip()}


class Context:
    """Last exchange kept so follow-up questions have conversation history."""
    def __init__(self, user_turn: str, assistant_turn: str) -> None:
        self.user_turn = user_turn
        self.assistant_turn = assistant_turn


def process_text(
    question: str,
    context: "Context | None" = None,
    briefing: "str | None" = None,
) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    client = Groq(api_key=GROQ_API_KEY)
    messages: list[dict] = [{"role": "system", "content": PROMPT}]

    brief_msg = _briefing_message(briefing)
    if brief_msg is not None:
        messages.append(brief_msg)

    if context is not None:
        messages.append({"role": "user",      "content": context.user_turn})
        messages.append({"role": "assistant", "content": context.assistant_turn})

    messages.append({"role": "user", "content": question})

    stream = client.chat.completions.create(
        model=GROQ_MODEL_TEXT,
        messages=messages,
        stream=True,
        max_tokens=1024,
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


def process(path: Path, briefing: "str | None" = None) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    client = Groq(api_key=GROQ_API_KEY)

    messages: list[dict] = []

    brief_msg = _briefing_message(briefing)
    if brief_msg is not None:
        messages.append(brief_msg)

    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
                {"type": "text", "text": PROMPT},
            ],
        }
    )

    stream = client.chat.completions.create(
        model=GROQ_MODEL_VISION,
        messages=messages,
        stream=True,
        max_tokens=1024,
    )

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token
