import base64
import json
from pathlib import Path
from typing import Iterator

import requests

from phonexi.config import OLLAMA_MODEL, OLLAMA_URL, PROMPT, TIMEOUT_S


class OllamaNotRunningError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


def process(path: Path) -> Iterator[str]:
    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": PROMPT,
        "images": [image_b64],
        "stream": True,
    }
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            stream=True,
            timeout=TIMEOUT_S,
        )
    except requests.exceptions.ConnectionError as exc:
        raise OllamaNotRunningError("Ollama is not running") from exc

    if response.status_code == 404:
        raise ModelNotFoundError(f"Model '{OLLAMA_MODEL}' not found")

    response.raise_for_status()

    try:
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("response", "")
            if token:
                yield token
            if chunk.get("done", False):
                break
    except requests.exceptions.Timeout:
        yield "\n[timeout]"
