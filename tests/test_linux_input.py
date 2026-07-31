from phonexi.backends.linux import _EvdevKeyStateMachine, KEY_P, KEY_RIGHTSHIFT, KEY_RIGHTALT, KEY_ESC


def _make():
    calls = {"screenshot": 0, "audio": 0, "close": 0}
    sm = _EvdevKeyStateMachine(
        on_screenshot=lambda: calls.__setitem__("screenshot", calls["screenshot"] + 1),
        on_audio_toggle=lambda: calls.__setitem__("audio", calls["audio"] + 1),
        on_close=lambda: calls.__setitem__("close", calls["close"] + 1),
    )
    return sm, calls


def test_right_shift_plus_p_fires_screenshot():
    sm, calls = _make()
    sm.process(KEY_RIGHTSHIFT, 1)  # down
    sm.process(KEY_P, 1)           # down
    assert calls["screenshot"] == 1
    assert calls["audio"] == 0


def test_right_alt_plus_p_fires_audio_toggle():
    sm, calls = _make()
    sm.process(KEY_RIGHTALT, 1)
    sm.process(KEY_P, 1)
    assert calls["audio"] == 1
    assert calls["screenshot"] == 0


def test_p_alone_fires_nothing():
    sm, calls = _make()
    sm.process(KEY_P, 1)
    assert calls == {"screenshot": 0, "audio": 0, "close": 0}


def test_escape_fires_close():
    sm, calls = _make()
    sm.process(KEY_ESC, 1)
    assert calls["close"] == 1


def test_held_p_repeat_does_not_refire():
    sm, calls = _make()
    sm.process(KEY_RIGHTSHIFT, 1)
    sm.process(KEY_P, 1)  # down
    sm.process(KEY_P, 2)  # autorepeat
    sm.process(KEY_P, 2)
    assert calls["screenshot"] == 1


def test_release_then_press_refires():
    sm, calls = _make()
    sm.process(KEY_RIGHTSHIFT, 1)
    sm.process(KEY_P, 1)
    sm.process(KEY_P, 0)  # release
    sm.process(KEY_P, 1)  # press again
    assert calls["screenshot"] == 2


def test_releasing_modifier_clears_it():
    sm, calls = _make()
    sm.process(KEY_RIGHTALT, 1)
    sm.process(KEY_RIGHTALT, 0)  # release alt
    sm.process(KEY_P, 1)         # P with no modifier now
    assert calls["audio"] == 0
