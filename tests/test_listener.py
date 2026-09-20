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
         patch("phonexi.listener.threading.Thread"), \
         patch.object(listener, "_stream_image"):

        mock_window_cls.return_value = MagicMock()
        listener._start_capture()

        mock_capture.assert_called_once()
        mock_window_cls.assert_called_once_with(root, use_primary=False)


def _drain(win):
    """Make an existing MagicMock window consume the stream it is handed."""
    win.show_and_collect.side_effect = lambda stream: "".join(stream)
    return win


def _consuming_window():
    """A view that drains the stream, like ResultWindow and WebView do."""
    win = MagicMock()
    win.show_and_collect.side_effect = lambda stream: "".join(stream)
    return win


def test_stream_image_calls_process_and_show(root):
    listener = HotkeyListener(tk_root=root)
    fake_path = MagicMock()
    mock_win = _consuming_window()

    with patch("phonexi.engines.api.process", return_value=iter(["hello"])) as mock_process:
        listener._stream_image(fake_path, mock_win)

    mock_process.assert_called_once_with(fake_path, briefing=None)
    mock_win.show_and_collect.assert_called_once()


def test_stream_image_handles_groq_not_configured(root):
    from phonexi.processor import GroqNotConfiguredError
    listener = HotkeyListener(tk_root=root)
    mock_win = MagicMock()

    with patch("phonexi.engines.api.process", side_effect=GroqNotConfiguredError()):
        listener._stream_image(MagicMock(), _drain(mock_win))

    root.update()
    mock_win.show_error.assert_called_once_with(
        "GROQ_API_KEY not set — add it to .env"
    )


def test_stream_image_handles_generic_error(root):
    listener = HotkeyListener(tk_root=root)
    mock_win = MagicMock()

    with patch("phonexi.engines.api.process", side_effect=RuntimeError("network fail")):
        listener._stream_image(MagicMock(), _drain(mock_win))

    root.update()
    mock_win.show_error.assert_called_once_with("Error: network fail")


def test_start_capture_forwards_use_primary(root):
    listener = HotkeyListener(tk_root=root, use_primary=True)

    with patch("phonexi.listener.capture", return_value=MagicMock()), \
         patch("phonexi.listener.ResultWindow") as mock_window_cls, \
         patch("phonexi.listener.threading.Thread"), \
         patch.object(listener, "_stream_image"):

        mock_window_cls.return_value = MagicMock()
        listener._start_capture()

        mock_window_cls.assert_called_once_with(root, use_primary=True)


def test_open_recording_popup_forwards_use_primary(root):
    listener = HotkeyListener(tk_root=root, use_primary=True)

    with patch("phonexi.listener.ResultWindow") as mock_window_cls:
        mock_window_cls.return_value = MagicMock()
        listener._open_recording_popup()

        mock_window_cls.assert_called_once_with(root, use_primary=True)


def test_view_factory_used_for_views():
    fake_view = MagicMock()
    listener = HotkeyListener(tk_root=None, view_factory=lambda: fake_view)
    with patch("phonexi.listener.capture", return_value=MagicMock()), \
         patch("phonexi.listener.threading.Thread"), \
         patch.object(listener, "_stream_image"):
        listener._start_capture()
    assert listener._current_window is fake_view


def test_schedule_runs_inline_without_tk():
    listener = HotkeyListener(tk_root=None, view_factory=lambda: MagicMock())
    called = []
    listener._schedule(lambda x: called.append(x), 7)
    assert called == [7]


def test_listener_defaults_to_no_briefing(root):
    listener = HotkeyListener(tk_root=root)
    assert listener._briefing is None


def test_listener_stores_briefing(root):
    listener = HotkeyListener(tk_root=root, briefing="Vacante Kafka.")
    assert listener._briefing == "Vacante Kafka."


def test_stream_image_forwards_briefing_to_process(root):
    listener = HotkeyListener(tk_root=root, briefing="Vacante Kafka.")

    with patch("phonexi.engines.api.process", return_value=iter([])) as mock_process:
        listener._stream_image(MagicMock(), _consuming_window())

    assert mock_process.call_args.kwargs["briefing"] == "Vacante Kafka."


def test_record_worker_forwards_briefing_to_process_text(root):
    listener = HotkeyListener(tk_root=root, briefing="Vacante Kafka.")
    win = _consuming_window()
    listener._current_window = win

    with patch("phonexi.listener.record", return_value=b"wav"), \
         patch("phonexi.listener.transcribe", return_value="¿Qué es un broker?"), \
         patch("phonexi.engines.api.process_text", return_value=iter([])) as mock_text:
        listener._record_worker(MagicMock())

    assert mock_text.call_args.kwargs["briefing"] == "Vacante Kafka."


def test_start_capture_passes_no_region_by_default(root):
    listener = HotkeyListener(tk_root=root)

    with patch("phonexi.listener.capture", return_value=MagicMock()) as mock_capture, \
         patch("phonexi.listener.ResultWindow"), \
         patch("phonexi.listener.threading.Thread"), \
         patch.object(listener, "_stream_image"):
        listener._start_capture()

    mock_capture.assert_called_once_with(region=None)


def test_start_capture_forwards_the_region(root):
    listener = HotkeyListener(tk_root=root, region=(1280, 720))

    with patch("phonexi.listener.capture", return_value=MagicMock()) as mock_capture, \
         patch("phonexi.listener.ResultWindow"), \
         patch("phonexi.listener.threading.Thread"), \
         patch.object(listener, "_stream_image"):
        listener._start_capture()

    mock_capture.assert_called_once_with(region=(1280, 720))


def test_stream_image_names_the_missing_gemini_key(root):
    from phonexi.processor import GroqNotConfiguredError
    listener = HotkeyListener(tk_root=root)
    mock_win = MagicMock()

    with patch("phonexi.engines.api.process",
               side_effect=GroqNotConfiguredError("GEMINI_API_KEY")):
        listener._stream_image(MagicMock(), _drain(mock_win))

    root.update()
    mock_win.show_error.assert_called_once_with(
        "GEMINI_API_KEY not set — add it to .env"
    )
