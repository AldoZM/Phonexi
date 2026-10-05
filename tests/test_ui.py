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


def test_popup_opens_in_the_top_right_corner(root):
    with patch("phonexi.ui.mss.MSS") as mock_mss:
        mock_mss.return_value.__enter__.return_value.monitors = [_VIRTUAL, _PRIMARY]
        win = ResultWindow(root, use_primary=True)
        win._win.update_idletasks()
        x = 1920 - ResultWindow._WIDTH - ResultWindow._MARGIN
        assert win._win.geometry().endswith(f"+{x}+{ResultWindow._MARGIN}")
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


def _tags_at(win, word, nth=0):
    """Tags on the nth occurrence of word in the rendered popup."""
    idx = "1.0"
    for _ in range(nth + 1):
        idx = win._text.search(word, idx, stopindex=tk.END)
        assert idx, f"{word!r} not rendered"
        found, idx = idx, f"{idx}+1c"
    return set(win._text.tag_names(found))


def test_compared_terms_get_different_highlight_colors(root):
    """In 'A vs B' both terms were the same yellow, so neither stood out."""
    win = ResultWindow(root)
    win._do_render("**TCP** is reliable; **UDP** is not.")
    tcp, udp = _tags_at(win, "TCP"), _tags_at(win, "UDP")
    assert "hl0" in tcp and "hl1" in udp
    assert win._text.tag_cget("hl0", "background") != win._text.tag_cget("hl1", "background")
    win._win.destroy()


def test_a_repeated_term_keeps_its_color(root):
    """Case and a trailing colon do not make it a new term."""
    win = ResultWindow(root)
    win._do_render("**TCP** vs **UDP**\n- **tcp:** ordered\n- **UDP:** fast")
    assert "hl0" in _tags_at(win, "tcp")
    assert "hl1" in _tags_at(win, "UDP", nth=1)
    win._win.destroy()


def test_highlight_colors_cycle_past_the_palette(root):
    win = ResultWindow(root)
    n = len(ResultWindow._HIGHLIGHTS)
    win._do_render(" ".join(f"**t{i}x**" for i in range(n + 1)))
    assert f"hl0" in _tags_at(win, f"t{n}x")
    win._win.destroy()


def test_code_inside_bold_loses_its_backticks(root):
    """**`acks=all`:** showed the backticks raw inside the highlight."""
    win = ResultWindow(root)
    win._do_render("- **`acks=all`:** waits for the ISR")
    assert "`" not in _widget_text(win)
    assert "hl0" in _tags_at(win, "acks=all")
    win._win.destroy()


def test_same_term_with_and_without_backticks_shares_a_color(root):
    win = ResultWindow(root)
    win._do_render("**`acks`** then **acks** then **other**")
    assert "hl0" in _tags_at(win, "acks", nth=1)
    assert "hl1" in _tags_at(win, "other")
    win._win.destroy()


def test_star_bullets_keep_their_bold_term(root):
    """'* **Pro:** x' read the bullet star as an italic opener."""
    win = ResultWindow(root)
    win._do_render("* **Pro:** decouples\n* plain `code` bullet")
    assert "*" not in _widget_text(win)
    assert "hl0" in _tags_at(win, "Pro:")
    win._win.destroy()


def test_italic_inside_bold_loses_its_stars(root):
    """**Salado de claves (*key salting*):** showed the stars inside the highlight."""
    win = ResultWindow(root)
    win._do_render("- **Salado de claves (*key salting*):** sufijo aleatorio")
    assert "*" not in _widget_text(win)
    assert "hl0" in _tags_at(win, "key salting")
    win._win.destroy()


# ── key phrases: one colour that means "say this" ───────────────────────────

def test_key_phrase_gets_the_key_highlight(root):
    win = ResultWindow(root)
    win._do_render("Order holds ==within each partition== only.")
    assert "=" not in _widget_text(win)
    assert "key" in _tags_at(win, "within each partition")
    win._win.destroy()


def test_labels_are_not_colored_when_the_answer_has_key_phrases(root):
    """Four bullet titles in four colours meant nothing (Kafka ordering answer)."""
    win = ResultWindow(root)
    win._do_render("- **Offsets:** ==strictly ordered== per partition\n- **Keys:** same key")
    for label in ("Offsets:", "Keys:"):
        tags = _tags_at(win, label)
        assert "strong" in tags
        assert not any(t.startswith("hl") for t in tags)
    win._win.destroy()


def test_comparisons_without_key_phrases_keep_per_term_colors(root):
    win = ResultWindow(root)
    win._do_render("- **TCP:** reliable\n- **UDP:** fast")
    assert "hl0" in _tags_at(win, "TCP:") and "hl1" in _tags_at(win, "UDP:")
    win._win.destroy()


def test_an_equality_in_prose_is_not_a_key_phrase(root):
    win = ResultWindow(root)
    win._do_render("if a == b and c == d then")
    assert "a == b and c == d" in _widget_text(win)
    win._win.destroy()


def _gated(gate, token):
    gate.wait(3)
    yield token


def test_the_waiting_line_can_be_set_per_mode(root):
    win = ResultWindow(root)
    gate = threading.Event()
    t = threading.Thread(
        target=lambda: win.show_and_collect(_gated(gate, "x"), status="Answering..."),
        daemon=True)
    t.start()
    try:
        assert _pump(root, lambda: "Answering..." in _widget_text(win))
        assert "screenshot" not in _widget_text(win)
    finally:
        gate.set()
    assert _pump(root, lambda: not t.is_alive())
    win._win.destroy()
