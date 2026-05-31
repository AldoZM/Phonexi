import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest
from phonexi.listener import HotkeyListener


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_hotkey_listener_accepts_tk_root(root):
    listener = HotkeyListener(tk_root=root)
    assert listener._tk_root is root


def test_start_capture_calls_capture_and_creates_window(root):
    listener = HotkeyListener(tk_root=root)
    fake_path = MagicMock()

    with patch("phonexi.listener.capture", return_value=fake_path) as mock_capture, \
         patch("phonexi.listener.ResultWindow") as mock_window_cls, \
         patch.object(listener, "_stream_to"):

        mock_window_cls.return_value = MagicMock()
        listener._start_capture()

        mock_capture.assert_called_once()
        mock_window_cls.assert_called_once_with(root)


def test_stream_to_calls_process_and_show(root):
    listener = HotkeyListener(tk_root=root)
    fake_path = MagicMock()
    fake_tokens = iter(["hello"])
    mock_win = MagicMock()

    with patch("phonexi.listener.process", return_value=fake_tokens) as mock_process:
        listener._stream_to(fake_path, mock_win)

    mock_process.assert_called_once_with(fake_path)
    mock_win.show.assert_called_once_with(fake_tokens)


def test_stream_to_handles_ollama_not_running(root):
    from phonexi.processor import OllamaNotRunningError
    listener = HotkeyListener(tk_root=root)
    mock_win = MagicMock()

    with patch("phonexi.listener.process", side_effect=OllamaNotRunningError()):
        listener._stream_to(MagicMock(), mock_win)

    root.update()  # flush after() queue
    mock_win.show_error.assert_called_once_with(
        "Ollama not running — start with: ollama serve"
    )


def test_stream_to_handles_model_not_found(root):
    from phonexi.processor import ModelNotFoundError
    listener = HotkeyListener(tk_root=root)
    mock_win = MagicMock()

    with patch("phonexi.listener.process", side_effect=ModelNotFoundError()):
        listener._stream_to(MagicMock(), mock_win)

    root.update()  # flush after() queue
    mock_win.show_error.assert_called_once_with(
        "Model not found — run: ollama pull llama3.2-vision:11b"
    )
