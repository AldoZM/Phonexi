from unittest.mock import patch

import pytest

from phonexi.processor import GroqNotConfiguredError


def test_transcribe_needs_the_groq_key_even_on_gemini():
    from phonexi import audio
    with patch("phonexi.audio.GROQ_API_KEY", ""), \
         patch("phonexi.audio.Groq") as groq_cls:
        with pytest.raises(GroqNotConfiguredError) as info:
            audio.transcribe(b"wav")
    groq_cls.assert_not_called()
    assert info.value.key_name == "GROQ_API_KEY"
