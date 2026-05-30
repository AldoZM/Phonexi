import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from phonexi.processor import ModelNotFoundError, OllamaNotRunningError, process


def _png(tmp_path: Path) -> Path:
    p = tmp_path / "shot.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    return p


def test_process_raises_when_ollama_not_running(tmp_path):
    img = _png(tmp_path)
    with patch("phonexi.processor.requests.post", side_effect=requests.exceptions.ConnectionError()):
        with pytest.raises(OllamaNotRunningError):
            list(process(img))


def test_process_raises_model_not_found(tmp_path):
    img = _png(tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.iter_lines.return_value = []
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        with pytest.raises(ModelNotFoundError):
            list(process(img))


def test_process_yields_tokens(tmp_path):
    img = _png(tmp_path)
    lines = [
        json.dumps({"response": "Hello", "done": False}).encode(),
        json.dumps({"response": " world", "done": False}).encode(),
        json.dumps({"response": "", "done": True}).encode(),
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = lines
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        tokens = list(process(img))
    assert tokens == ["Hello", " world"]


def test_process_stops_at_done_true(tmp_path):
    img = _png(tmp_path)
    lines = [
        json.dumps({"response": "A", "done": True}).encode(),
        json.dumps({"response": "B", "done": False}).encode(),
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = lines
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        tokens = list(process(img))
    assert tokens == ["A"]


def test_process_yields_timeout_sentinel_on_read_timeout(tmp_path):
    img = _png(tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    def _slow_lines():
        yield json.dumps({"response": "partial", "done": False}).encode()
        raise requests.exceptions.Timeout()

    mock_resp.iter_lines.return_value = _slow_lines()
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        tokens = list(process(img))
    assert "partial" in tokens
    assert tokens[-1] == "\n[timeout]"


def test_process_encodes_image_as_base64(tmp_path):
    import base64
    img = _png(tmp_path)
    raw = img.read_bytes()
    expected_b64 = base64.b64encode(raw).decode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        json.dumps({"response": "ok", "done": True}).encode()
    ]
    with patch("phonexi.processor.requests.post", return_value=mock_resp) as mock_post:
        list(process(img))
    payload = mock_post.call_args.kwargs["json"]
    assert payload["images"] == [expected_b64]
