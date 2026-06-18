import tkinter as tk
import pytest
from unittest.mock import patch
from phonexi.ui import ResultWindow


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_result_window_title(root):
    win = ResultWindow(root)
    assert win._win.title() == "Phonexi"
    win._win.destroy()


def test_result_window_is_topmost(root):
    win = ResultWindow(root)
    assert win._win.attributes("-topmost") == 1
    win._win.destroy()


def test_result_window_has_show_method(root):
    win = ResultWindow(root)
    assert callable(win.show)
    win._win.destroy()


def test_result_window_has_show_error_method(root):
    win = ResultWindow(root)
    assert callable(win.show_error)
    win._win.destroy()


def test_show_error_inserts_message(root):
    win = ResultWindow(root)
    win.show_error("test error message")
    content = win._text.get("1.0", tk.END)
    assert "test error message" in content
    win._win.destroy()


def test_insert_appends_text(root):
    win = ResultWindow(root)
    win._ins("hello")
    win._ins(" world")
    content = win._text.get("1.0", tk.END)
    assert "hello world" in content
    win._win.destroy()


_VIRTUAL   = {"left": 0, "top": 0, "width": 100, "height": 100}
_PRIMARY   = {"left": 0, "top": 0, "width": 1920, "height": 1080, "is_primary": True}
_SECONDARY = {"left": 1920, "top": 0, "width": 1920, "height": 1080, "is_primary": False}


def test_target_monitor_primary(root):
    with patch("phonexi.ui.mss.MSS") as mock_mss:
        mock_mss.return_value.__enter__.return_value.monitors = [_VIRTUAL, _PRIMARY, _SECONDARY]
        win = ResultWindow(root, use_primary=True)
        assert win._target_monitor() == _PRIMARY
        win._win.destroy()


def test_target_monitor_secondary_default(root):
    with patch("phonexi.ui.mss.MSS") as mock_mss:
        mock_mss.return_value.__enter__.return_value.monitors = [_VIRTUAL, _PRIMARY, _SECONDARY]
        win = ResultWindow(root)
        assert win._target_monitor() == _SECONDARY
        win._win.destroy()


def test_target_monitor_single_display_fallback(root):
    with patch("phonexi.ui.mss.MSS") as mock_mss:
        mock_mss.return_value.__enter__.return_value.monitors = [_VIRTUAL, _PRIMARY]
        win = ResultWindow(root, use_primary=False)
        assert win._target_monitor() == _PRIMARY
        win._win.destroy()


def test_result_window_close_destroys(root):
    win = ResultWindow(root)
    win.close()
    assert not win._win.winfo_exists()
