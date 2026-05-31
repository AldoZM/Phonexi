import base64
from pathlib import Path
from typing import Iterator

from groq import Groq

from phonexi.config import GROQ_API_KEY, GROQ_MODEL, PROMPT


class GroqNotConfiguredError(Exception):
    pass


class GroqAPIError(Exception):
    pass


def process_text(question: str) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    client = Groq(api_key=GROQ_API_KEY)
    system = (
        "Respond in the same language as the question. "
        "Be extremely brief. Answer only what is asked. "
        "No greetings, no preamble, no summaries. "
        "One sentence max for simple questions."
    )
    stream = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
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
        model=GROQ_MODEL,
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
