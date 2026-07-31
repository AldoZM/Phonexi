import subprocess
from pathlib import Path
from typing import Iterator

from groq import Groq

from phonexi.config import (
    GROQ_API_KEY,
    GROQ_MODEL_TEXT,
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


def _ocr_image(path: Path) -> str:
    """Extract text from a screenshot with the tesseract CLI."""
    try:
        result = subprocess.run(
            ["tesseract", str(path), "stdout"],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError:
        raise GroqAPIError(
            "tesseract not found — install it (sudo apt install tesseract-ocr)"
        )
    except subprocess.CalledProcessError as exc:
        raise GroqAPIError(f"OCR failed: {exc.stderr.strip()}")
    return result.stdout


def process(path: Path) -> Iterator[str]:
    """Screenshot mode: OCR the image, then answer via the text model.

    Groq no longer offers a vision model on the free tier, so screenshots are
    read with tesseract and the extracted text is sent to the text LLM.
    """
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    text = _ocr_image(path).strip()
    if not text:
        raise GroqAPIError("No text found in screenshot (OCR returned empty)")

    yield from process_text(text)
