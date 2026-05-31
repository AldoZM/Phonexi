from phonexi import config


def test_ollama_url():
    assert config.OLLAMA_URL == "http://localhost:11434"


def test_ollama_model():
    assert config.OLLAMA_MODEL == "llava:7b"


def test_timeout():
    assert isinstance(config.TIMEOUT_S, int)
    assert config.TIMEOUT_S > 0


def test_prompt_is_string():
    assert isinstance(config.PROMPT, str)
    assert len(config.PROMPT) > 0
