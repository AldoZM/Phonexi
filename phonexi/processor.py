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


class Context:
    """Last exchange kept so follow-up questions have conversation history."""
    def __init__(self, user_turn: str, assistant_turn: str) -> None:
        self.user_turn = user_turn
        self.assistant_turn = assistant_turn


def process_text(question: str, context: "Context | None" = None) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    client = Groq(api_key=GROQ_API_KEY)
    messages: list[dict] = [{"role": "system", "content": PROMPT}]

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


def process(path: Path) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    client = Groq(api_key=GROQ_API_KEY)

    stream = client.chat.completions.create(
        model=GROQ_MODEL_VISION,
        messages=[
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
        ],
        stream=True,
        max_tokens=1024,
    )

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token
