from pathlib import Path
from typing import Iterator

from google import genai
from google.genai import types
from PIL import Image

from phonexi.config import GEMINI_API_KEY, GEMINI_MODEL, PROMPT


class GeminiNotConfiguredError(Exception):
    pass


class GeminiAPIError(Exception):
    pass


def process(path: Path) -> Iterator[str]:
    if not GEMINI_API_KEY:
        raise GeminiNotConfiguredError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=GEMINI_API_KEY)
    image = Image.open(path)

    response = client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=[PROMPT, image],
    )
    for chunk in response:
        text = chunk.text
        if text:
            yield text
