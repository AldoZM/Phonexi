from array import array
from unittest.mock import patch

import pytest

from phonexi import audio
from phonexi.processor import GroqNotConfiguredError


def test_transcribe_needs_the_groq_key_even_on_gemini():
    from phonexi import audio
    with patch("phonexi.audio.GROQ_API_KEY", ""), \
         patch("phonexi.audio.Groq") as groq_cls:
        with pytest.raises(GroqNotConfiguredError) as info:
            audio.transcribe(b"wav")
    groq_cls.assert_not_called()
    assert info.value.key_name == "GROQ_API_KEY"


def _pcm(samples: "list[int]") -> bytes:
    return array("h", samples).tobytes()


def _samples(raw: bytes) -> "list[int]":
    return array("h", raw).tolist()


def test_stereo_48k_is_averaged_and_decimated_to_16k():
    # Two channels average, then every third frame survives: 48000/16000 == 3.
    raw = _pcm([100, 200,  300, 400,  500, 600,  700, 800,  900, 1000,  1100, 1200])
    out, rate = audio._to_mono_16k(raw, 2, 48000)
    assert _samples(out) == [150, 750]
    assert rate == 16000


def test_mono_input_is_only_decimated():
    raw = _pcm([1, 2, 3, 4, 5, 6])
    out, rate = audio._to_mono_16k(raw, 1, 48000)
    assert _samples(out) == [1, 4]
    assert rate == 16000


def test_audio_already_at_the_target_rate_is_left_alone():
    raw = _pcm([10, 20, 30, 40])
    out, rate = audio._to_mono_16k(raw, 2, 16000)
    assert _samples(out) == [15, 35]
    assert rate == 16000


def test_44100_decimates_by_three_and_reports_the_rate_it_got():
    # round(44100/16000) == 3, so the real rate is 14700, not 16000. Whisper is
    # told the truth or it plays the audio back at the wrong speed.
    raw = _pcm(list(range(12)))
    out, rate = audio._to_mono_16k(raw, 1, 44100)
    assert _samples(out) == [0, 3, 6, 9]
    assert rate == 14700


def test_channel_average_floors_negative_samples():
    # -201 // 2 == -101, not -100. Pinned because numpy and Python must agree.
    raw = _pcm([-101, -100, 7, 8])
    out, _ = audio._to_mono_16k(raw, 2, 16000)
    assert _samples(out) == [-101, 7]


def test_a_trailing_half_frame_is_dropped_not_halved():
    # WASAPI hands back whole frames, so this never happens in production. It is
    # pinned because the obvious averaging loop emits 500//2 as a real sample.
    raw = _pcm([100, 200, 300, 400, 500])
    out, _ = audio._to_mono_16k(raw, 2, 16000)
    assert _samples(out) == [150, 350]
