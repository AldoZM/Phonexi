from phonexi import config


def test_groq_model_is_string():
    assert isinstance(config.GROQ_MODEL, str)
    assert len(config.GROQ_MODEL) > 0


def test_groq_api_key_is_string():
    assert isinstance(config.GROQ_API_KEY, str)


def test_prompt_is_string():
    assert isinstance(config.PROMPT, str)
    assert len(config.PROMPT) > 0
