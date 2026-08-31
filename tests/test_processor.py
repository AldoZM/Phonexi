from pathlib import Path
from unittest.mock import MagicMock, patch
import base64

import pytest

from phonexi.processor import (
    Context,
    GroqNotConfiguredError,
    _briefing_message,
    process,
    process_text,
)


def _png(tmp_path: Path) -> Path:
    p = tmp_path / "shot.png"
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    p.write_bytes(base64.b64decode(png_b64))
    return p


def test_process_raises_when_key_missing(tmp_path):
    img = _png(tmp_path)
    with patch("phonexi.processor.GROQ_API_KEY", ""):
        with pytest.raises(GroqNotConfiguredError):
            list(process(img))


def test_process_yields_tokens(tmp_path):
    img = _png(tmp_path)

    chunk1 = MagicMock()
    chunk1.choices[0].delta.content = "Hello"
    chunk2 = MagicMock()
    chunk2.choices[0].delta.content = " world"
    chunk3 = MagicMock()
    chunk3.choices[0].delta.content = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([chunk1, chunk2, chunk3])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        tokens = list(process(img))

    assert tokens == ["Hello", " world"]


def test_process_calls_correct_model(tmp_path):
    img = _png(tmp_path)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        list(process(img))

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "qwen" in call_kwargs["model"]
    assert call_kwargs["stream"] is True


def _messages_from(mock_client) -> list:
    return mock_client.chat.completions.create.call_args.kwargs["messages"]


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = iter([])
    return client


def test_process_text_without_briefing_sends_single_system_message():
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process_text("¿Qué es un consumer group?"))

    systems = [m for m in _messages_from(client) if m["role"] == "system"]
    assert len(systems) == 1


def test_process_text_sends_briefing_as_extra_system_message():
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process_text("¿Qué es un consumer group?", briefing="Vacante Kafka."))

    systems = [m for m in _messages_from(client) if m["role"] == "system"]
    assert len(systems) == 2
    assert "Vacante Kafka." in systems[1]["content"]


def test_process_text_puts_briefing_before_the_question():
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process_text("La pregunta", briefing="El contexto"))

    roles = [m["role"] for m in _messages_from(client)]
    assert roles == ["system", "system", "user"]


def test_process_text_keeps_briefing_ahead_of_conversation_context():
    client = _mock_client()
    ctx = Context(user_turn="pregunta previa", assistant_turn="respuesta previa")
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process_text("nueva", context=ctx, briefing="El contexto"))

    roles = [m["role"] for m in _messages_from(client)]
    assert roles == ["system", "system", "user", "assistant", "user"]


def test_process_without_briefing_sends_no_system_message(tmp_path):
    img = _png(tmp_path)
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process(img))

    assert [m["role"] for m in _messages_from(client)] == ["user"]


def test_process_sends_briefing_as_system_message(tmp_path):
    img = _png(tmp_path)
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process(img, briefing="Vacante Kafka."))

    messages = _messages_from(client)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "Vacante Kafka." in messages[0]["content"]


def test_process_still_sends_the_image_when_briefing_present(tmp_path):
    img = _png(tmp_path)
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process(img, briefing="Vacante Kafka."))

    user_content = _messages_from(client)[-1]["content"]
    assert any(part["type"] == "image_url" for part in user_content)


def test_briefing_message_forbids_naming_the_context():
    """The answer must read as the candidate's own knowledge, never as a citation."""
    content = _briefing_message("Vacante Kafka.")["content"].lower()
    assert "never mention" in content
    assert "your own knowledge" in content


def test_prompt_forbids_meta_preamble():
    from phonexi.config import PROMPT
    assert "never refer to" in PROMPT.lower()
