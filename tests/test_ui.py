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


# ── a closed popup must not crash the callback that arrives late ────────────
# A CLI engine answers in 9-30s, so Escape (or a second capture) lands in that
# window far more often than it did with Groq's near-instant reply.

def test_render_after_close_does_not_raise(root):
    win = ResultWindow(root)
    win._win.destroy()
    win._do_render("# Answer\n\nsome text")


def test_status_after_close_does_not_raise(root):
    win = ResultWindow(root)
    win._win.destroy()
    win.show_status("Listening...")


def test_error_after_close_does_not_raise(root):
    win = ResultWindow(root)
    win._win.destroy()
    win.show_error("Antigravity (agy): something broke")


# ── progressive popup: text shows while it streams ──────────────────────────

import threading
import time


def _widget_text(win):
    return win._text.get("1.0", "end-1c")


def _pump(root, until, timeout=3.0):
    """Run a real mainloop until until() holds.

    root.after from a worker thread only works while the Tk thread sits in
    mainloop; an update() loop raises "main thread is not in main loop".
    """
    end = time.monotonic() + timeout
    held = {"ok": False}

    def check():
        if until():
            held["ok"] = True
            root.quit()
        elif time.monotonic() > end:
            root.quit()
        else:
            root.after(10, check)

    root.after(10, check)
    root.mainloop()
    return held["ok"]


def _held_stream(first, gate, rest):
    def gen():
        yield first
        gate.wait(3)
        yield from rest
    return gen()


def test_first_tokens_show_before_the_answer_ends(root):
    win = ResultWindow(root)
    gate = threading.Event()
    result = {}
    t = threading.Thread(
        target=lambda: result.setdefault("r", win.show_and_collect(
            _held_stream("Use a hash map", gate, [" and a list."]))),
        daemon=True,
    )
    t.start()
    try:
        assert _pump(root, lambda: "Use a hash map" in _widget_text(win)), \
            "nothing appeared while the answer was still streaming"
    finally:
        gate.set()
    assert _pump(root, lambda: not t.is_alive())
    assert result["r"] == "Use a hash map and a list."
    win._win.destroy()


def test_the_status_line_goes_away_on_the_first_token(root):
    win = ResultWindow(root)
    gate = threading.Event()
    t = threading.Thread(
        target=lambda: win.show_and_collect(_held_stream("Answer", gate, [])), daemon=True)
    t.start()
    try:
        assert _pump(root, lambda: "Answer" in _widget_text(win))
        assert "Analyzing" not in _widget_text(win)
    finally:
        gate.set()
    assert _pump(root, lambda: not t.is_alive())
    win._win.destroy()


def _collect_in_worker(root, win, tokens):
    # The listener calls show_and_collect off the Tk thread while mainloop
    # runs; calling it on the Tk thread here would deadlock the test.
    t = threading.Thread(target=lambda: win.show_and_collect(tokens), daemon=True)
    t.start()
    assert _pump(root, lambda: not t.is_alive()), "show_and_collect never returned"
    root.update()


def test_the_final_render_replaces_the_raw_stream(root):
    win = ResultWindow(root)
    _collect_in_worker(root, win, iter(["**bold**", " text"]))
    assert _pump(root, lambda: "bold text" in _widget_text(win))
    assert "**" not in _widget_text(win)
    win._win.destroy()


def test_streaming_into_a_closed_popup_does_not_raise(root):
    win = ResultWindow(root)
    win.close()
    _collect_in_worker(root, win, iter(["late", " tokens"]))
