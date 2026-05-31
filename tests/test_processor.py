from pathlib import Path
from unittest.mock import MagicMock, patch
import base64

import pytest

from phonexi.processor import GroqNotConfiguredError, process


def _png(tmp_path: Path) -> Path:
    p = tmp_path / "shot.png"
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    p.write_bytes(base64.b64decode(png_b64))
    return p


def test_process_raises_when_key_missing(tmp_path):
    img = _png(tmp_path)
    with patch("phonexi.processor.GROQ_API_KEY", ""):
        with pytest.raises(GroqNotConfiguredError):
            list(process(img))


def test_process_yields_tokens(tmp_path):
    img = _png(tmp_path)

    chunk1 = MagicMock()
    chunk1.choices[0].delta.content = "Hello"
    chunk2 = MagicMock()
    chunk2.choices[0].delta.content = " world"
    chunk3 = MagicMock()
    chunk3.choices[0].delta.content = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([chunk1, chunk2, chunk3])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        tokens = list(process(img))

    assert tokens == ["Hello", " world"]


def test_process_calls_correct_model(tmp_path):
    img = _png(tmp_path)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        list(process(img))

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "llama-4-scout" in call_kwargs["model"]
    assert call_kwargs["stream"] is True
