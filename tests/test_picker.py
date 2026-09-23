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


def test_the_header_names_what_is_being_chosen():
    out = io.StringIO()
    keys = iter(ENTER)
    choose(MODELS, read_key=lambda: next(keys), out=out, is_tty=True, what="CLI")
    assert "Choose a CLI" in out.getvalue()


def test_the_header_still_says_model_by_default():
    out = io.StringIO()
    keys = iter(ENTER)
    choose(MODELS, read_key=lambda: next(keys), out=out, is_tty=True)
    assert "Choose a model" in out.getvalue()


def test_the_no_console_error_names_the_flag_that_was_used():
    with pytest.raises(PickerUnavailableError) as exc:
        choose(MODELS, is_tty=False, what="CLI")
    assert "-cli needs" in str(exc.value)


# ── Left/Right: effort levels on rows that have them ────────────────────────

from phonexi.engines.base import CliChoice

LEFT = ["\xe0", "K"]
RIGHT = ["\xe0", "M"]
LEVELS = ("low", "medium", "high")
CLI_ROWS = [
    CliChoice("agy", "Gemini 3.8 Flash", LEVELS, "medium",
              tuple((l, f"gemini-3.8-flash-{l}") for l in LEVELS)),
    CliChoice("agy", "Claude Sonnet 4.6", (), "", (("", "claude-sonnet-4-6"),)),
    CliChoice("claude", "Claude Code", LEVELS, "medium"),
]


def _pick_cli(keys):
    it = iter(keys)
    out = io.StringIO()
    result = choose(CLI_ROWS, read_key=lambda: next(it), out=out, is_tty=True, what="CLI")
    return result, out.getvalue()


def test_right_raises_the_level():
    result, _ = _pick_cli(RIGHT + ENTER)
    assert result.level == "high"
    assert result.model_id == "gemini-3.8-flash-high"


def test_left_lowers_the_level():
    result, _ = _pick_cli(LEFT + ENTER)
    assert result.level == "low"


def test_level_stops_at_both_ends():
    assert _pick_cli(LEFT * 4 + ENTER)[0].level == "low"
    assert _pick_cli(RIGHT * 4 + ENTER)[0].level == "high"


def test_each_row_keeps_its_own_level():
    result, _ = _pick_cli(RIGHT + DOWN + DOWN + LEFT + UP + UP + ENTER)
    assert result.name == "Gemini 3.8 Flash"
    assert result.level == "high"


def test_left_right_is_ignored_on_a_row_without_levels():
    result, _ = _pick_cli(DOWN + LEFT + RIGHT + ENTER)
    assert result is CLI_ROWS[1]


def test_level_is_drawn_between_arrows():
    _, text = _pick_cli(RIGHT + ENTER)
    rows = [re.sub(r"\x1b\[\d*[A-Z]", "", l) for l in text.splitlines()]
    assert [r for r in rows if "Gemini 3.8 Flash" in r][-1].endswith("< high >")


def test_header_mentions_left_right_only_when_a_row_has_levels():
    _, cli_text = _pick_cli(ENTER)
    _, model_text = _pick(ENTER)
    assert "Left/Right" in cli_text.splitlines()[0]
    assert "Left/Right" not in model_text.splitlines()[0]
