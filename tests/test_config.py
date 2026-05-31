from phonexi import config


def test_gemini_model_is_string():
    assert isinstance(config.GEMINI_MODEL, str)
    assert len(config.GEMINI_MODEL) > 0


def test_gemini_api_key_is_string():
    assert isinstance(config.GEMINI_API_KEY, str)


def test_prompt_is_string():
    assert isinstance(config.PROMPT, str)
    assert len(config.PROMPT) > 0
