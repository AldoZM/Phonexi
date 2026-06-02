import base64
from pathlib import Path
from typing import Iterator

from groq import Groq

from phonexi.config import GROQ_API_KEY, GROQ_MODEL, PROMPT


class GroqNotConfiguredError(Exception):
    pass


class GroqAPIError(Exception):
    pass


class Context:
    """Last exchange kept so follow-up questions have conversation history."""
    def __init__(self, user_turn: str, assistant_turn: str) -> None:
        self.user_turn = user_turn
        self.assistant_turn = assistant_turn


_SYSTEM = (
    "You are helping someone answer a technical job interview question. "
    "Respond in the same language as the question. "
    "Give a confident, correct answer that demonstrates clear understanding — "
    "the kind a strong senior developer would give in an interview. "
    "No filler, no greetings, no examples unless the question specifically requires one. "
    "Get to the point immediately. "
    "When your answer includes code, every logical section must have a comment explaining "
    "what it does and WHY that implementation decision was made — "
    "write the comments as if teaching a junior developer, showing mastery of the topic. "
    "Comments must be in the same language as the question. "
    "If the input contains multiple questions, answer each one in its own clearly separated section: "
    "use a numbered heading (e.g. '1.', '2.') and a divider line of dashes (---) between sections "
    "so each answer is visually distinct and easy to read independently."
)


def process_text(question: str, context: "Context | None" = None) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    client = Groq(api_key=GROQ_API_KEY)
    messages: list[dict] = [{"role": "system", "content": _SYSTEM}]

    if context is not None:
        messages.append({"role": "user",      "content": context.user_turn})
        messages.append({"role": "assistant", "content": context.assistant_turn})

    messages.append({"role": "user", "content": question})

    stream = client.chat.completions.create(
        model=GROQ_MODEL,
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
