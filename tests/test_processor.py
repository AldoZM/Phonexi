from pathlib import Path
from unittest.mock import MagicMock, patch
import base64

import pytest

from phonexi.processor import GeminiNotConfiguredError, process


def _png(tmp_path: Path) -> Path:
    p = tmp_path / "shot.png"
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    p.write_bytes(base64.b64decode(png_b64))
    return p


def test_process_raises_when_key_missing(tmp_path):
    img = _png(tmp_path)
    with patch("phonexi.processor.GEMINI_API_KEY", ""):
        with pytest.raises(GeminiNotConfiguredError):
            list(process(img))


def test_process_yields_tokens(tmp_path):
    img = _png(tmp_path)

    chunk1 = MagicMock()
    chunk1.text = "Hello"
    chunk2 = MagicMock()
    chunk2.text = " world"
    chunk3 = MagicMock()
    chunk3.text = None

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = iter([chunk1, chunk2, chunk3])

    with patch("phonexi.processor.GEMINI_API_KEY", "fake-key"), \
         patch("phonexi.processor.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        tokens = list(process(img))

    assert tokens == ["Hello", " world"]


def test_process_calls_generate_with_correct_model(tmp_path):
    img = _png(tmp_path)

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = iter([])

    with patch("phonexi.processor.GEMINI_API_KEY", "fake-key"), \
         patch("phonexi.processor.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        list(process(img))

    mock_client.models.generate_content_stream.assert_called_once()
    call_kwargs = mock_client.models.generate_content_stream.call_args
    assert call_kwargs.kwargs["model"] == "gemini-2.0-flash"
