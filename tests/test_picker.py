import io
import re

import pytest

from phonexi.picker import PickerUnavailableError, choose
from phonexi.providers import GEMINI, GROQ, Model

MODELS = [
    Model(GEMINI, "gemini-a", vision=True, audio=True),
    Model(GEMINI, "gemini-b", vision=True, audio=True),
    Model(GROQ, "groq-c", vision=False, audio=False),
]

UP = ["\xe0", "H"]
DOWN = ["\xe0", "P"]
ENTER = ["\r"]
ESC = ["\x1b"]


def _pick(keys, start=0):
    it = iter(keys)
    out = io.StringIO()
    result = choose(MODELS, start=start, read_key=lambda: next(it), out=out, is_tty=True)
    return result, out.getvalue()


def test_enter_picks_the_first_model():
    result, _ = _pick(ENTER)
    assert result is MODELS[0]


def test_down_moves_the_cursor():
    result, _ = _pick(DOWN + DOWN + ENTER)
    assert result is MODELS[2]


def test_up_moves_back():
    result, _ = _pick(DOWN + DOWN + UP + ENTER)
    assert result is MODELS[1]


def test_cursor_stops_at_the_top():
    result, _ = _pick(UP + UP + ENTER)
    assert result is MODELS[0]


def test_cursor_stops_at_the_bottom():
    result, _ = _pick(DOWN * 5 + ENTER)
    assert result is MODELS[2]


def test_escape_cancels():
    result, _ = _pick(ESC)
    assert result is None


def test_ctrl_c_cancels():
    result, _ = _pick(["\x03"])
    assert result is None


def test_other_keys_are_ignored():
    result, _ = _pick(["x", "\x00", "K"] + DOWN + ENTER)
    assert result is MODELS[1]


def test_start_places_the_cursor():
    result, _ = _pick(ENTER, start=2)
    assert result is MODELS[2]


def test_the_cursor_row_is_marked_with_gt():
    _, text = _pick(DOWN + ENTER)
    rows = [re.sub(r"\x1b\[\d*[A-Z]", "", l) for l in text.splitlines()]
    assert [r for r in rows if "gemini-b" in r][-1].startswith(">")
    assert [r for r in rows if "gemini-a" in r][-1].startswith(" ")


def test_capabilities_are_shown():
    _, text = _pick(ENTER)
    assert "text, vision, audio" in text


def test_refuses_without_a_terminal():
    with pytest.raises(PickerUnavailableError):
        choose(MODELS, read_key=lambda: "\r", out=io.StringIO(), is_tty=False)


def test_refuses_an_empty_list():
    with pytest.raises(PickerUnavailableError):
        choose([], read_key=lambda: "\r", out=io.StringIO(), is_tty=True)
