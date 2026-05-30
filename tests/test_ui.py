import tkinter as tk
import pytest
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
    win._insert("hello")
    win._insert(" world")
    content = win._text.get("1.0", tk.END)
    assert "hello world" in content
    win._win.destroy()
