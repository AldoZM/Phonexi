from pathlib import Path
from unittest.mock import MagicMock, patch
import base64

import pytest

from phonexi.processor import GroqAPIError, GroqNotConfiguredError, process


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


def test_process_ocrs_then_feeds_text_to_model(tmp_path):
    img = _png(tmp_path)

    chunk1 = MagicMock(); chunk1.choices[0].delta.content = "4"
    chunk2 = MagicMock(); chunk2.choices[0].delta.content = None
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor._ocr_image", return_value="What is 2+2?"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        tokens = list(process(img))

    assert tokens == ["4"]
    call = mock_client.chat.completions.create.call_args.kwargs
    # OCR text becomes the user question sent to the text model
    assert call["messages"][-1]["content"] == "What is 2+2?"


def test_process_uses_text_model(tmp_path):
    img = _png(tmp_path)
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor._ocr_image", return_value="question"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        list(process(img))

    call = mock_client.chat.completions.create.call_args.kwargs
    assert "llama-3.3-70b" in call["model"]
    assert call["stream"] is True


def test_process_raises_when_ocr_empty(tmp_path):
    img = _png(tmp_path)
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor._ocr_image", return_value="   \n  "):
        with pytest.raises(GroqAPIError, match="[Nn]o text"):
            list(process(img))
