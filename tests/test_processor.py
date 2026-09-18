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


def test_prompt_forbids_inventing_facts():
    """An invented number survives the popup and dies in the follow-up question."""
    from phonexi.config import PROMPT
    low = PROMPT.lower()
    assert "never invent" in low
    assert "do not recall" in low


def test_prompt_asks_for_wire_level_answers():
    from phonexi.config import PROMPT
    assert "wire-format level" in PROMPT.lower()


def test_prompt_forbids_invented_metrics():
    """gpt-oss-120b invented a 90% reduction and 10k TPS that no context stated."""
    from phonexi.config import PROMPT
    low = PROMPT.lower()
    assert "percentages" in low
    assert "throughput figures" in low


def test_prompt_forbids_markdown_tables():
    """The popup renders a markdown table as a wall of pipes."""
    from phonexi.config import PROMPT
    assert "no markdown tables" in PROMPT.lower()


def test_prompt_forbids_vague_magnitudes():
    """"Varios miles por segundo" slipped past the percentages rule."""
    from phonexi.config import PROMPT
    low = PROMPT.lower()
    assert "orders of magnitude" in low
    assert "vague quantities" in low


_SEP = "=" * 60
_SECTIONED_BRIEFING = "\n".join([
    _SEP, "FICHA DE REFERENCIA", _SEP, "",
    "COMO USAR ESTA FICHA", "Responde exactamente lo que te preguntan.", "",
    _SEP, "1. CONSUMER LAG", _SEP, "",
    "El lag es la diferencia entre el ultimo offset y el confirmado.", "",
    _SEP, "2. INDICES EN MYSQL", _SEP, "",
    "Un covering index cubre todas las columnas del select.",
])


def test_process_text_sends_only_the_sections_the_question_touches():
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process_text("como mides el consumer lag?", briefing=_SECTIONED_BRIEFING))

    briefing_msg = [m for m in _messages_from(client) if m["role"] == "system"][1]
    assert "1. CONSUMER LAG" in briefing_msg["content"]
    assert "2. INDICES EN MYSQL" not in briefing_msg["content"]


def test_process_text_keeps_the_usage_rules_of_the_ficha():
    client = _mock_client()
    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=client):
        list(process_text("como mides el consumer lag?", briefing=_SECTIONED_BRIEFING))

    briefing_msg = [m for m in _messages_from(client) if m["role"] == "system"][1]
    assert "Responde exactamente lo que te preguntan." in briefing_msg["content"]


def _rate_limit_error(body: str):
    """Build a RateLimitError the way the Groq SDK surfaces a real 429."""
    import httpx
    from groq import RateLimitError

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, text=body)
    return RateLimitError(body, response=response, body=None)


def test_rate_limit_message_names_the_output_allowance():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_error(
        "Request too large for model `qwen/qwen3.8-27b` on output tokens per "
        "minute (OTPM): Limit 1000, Requested 1024."
    )
    msg = _rate_limit_message(exc)

    assert "answer-length allowance" in msg
    assert "Limit 1000" not in msg
    assert len(msg) < 160


def test_rate_limit_message_keeps_the_retry_delay():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_error(
        "Rate limit reached for model on tokens per minute (TPM). "
        "Please try again in 8.5s."
    )
    msg = _rate_limit_message(exc)

    assert "8.5s" in msg


def test_process_text_converts_rate_limit_to_groq_api_error():
    from phonexi.processor import GroqAPIError

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = _rate_limit_error(
        "on output tokens per minute (OTPM): Limit 1000, Requested 1024."
    )

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        with pytest.raises(GroqAPIError) as caught:
            list(process_text("question"))

    assert "answer-length allowance" in str(caught.value)


def test_process_converts_rate_limit_to_groq_api_error(tmp_path):
    from phonexi.processor import GroqAPIError

    img = _png(tmp_path)
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = _rate_limit_error(
        "on tokens per minute (TPM). Please try again in 3s."
    )

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        with pytest.raises(GroqAPIError) as caught:
            list(process(img))

    assert "3s" in str(caught.value)


def _bad_request(message: str):
    """Build the 400 the API returns when a model rejects a reasoning level."""
    import httpx
    from groq import BadRequestError

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(400, request=request, text=message)
    return BadRequestError(message, response=response, body=None)


def test_reasoning_effort_is_sent_to_the_model():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.GROQ_REASONING_TEXT", "low"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        list(process_text("question"))

    assert mock_client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "low"


def test_unsupported_reasoning_effort_is_dropped_and_retried():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _bad_request("`reasoning_effort` must be one of `none` or `default`"),
        iter([]),
    ]

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.GROQ_REASONING_TEXT", "low"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        list(process_text("question"))

    assert mock_client.chat.completions.create.call_count == 2
    assert "reasoning_effort" not in mock_client.chat.completions.create.call_args.kwargs


def test_unrelated_bad_request_is_not_swallowed():
    from groq import BadRequestError

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = _bad_request(
        "messages[0].content must be a string"
    )

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.GROQ_REASONING_TEXT", "low"), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        with pytest.raises(BadRequestError):
            list(process_text("question"))

    assert mock_client.chat.completions.create.call_count == 1


def test_empty_reasoning_effort_sends_nothing(tmp_path):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.GROQ_REASONING_VISION", ""), \
         patch("phonexi.processor.Groq", return_value=mock_client):
        list(process(_png(tmp_path)))

    assert "reasoning_effort" not in mock_client.chat.completions.create.call_args.kwargs


def _rate_limit_with_headers(body: str, headers: dict):
    """A 429 carrying the rate-limit headers Groq actually returns."""
    import httpx
    from groq import RateLimitError

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, text=body, headers=headers)
    return RateLimitError(body, response=response, body=None)


# ── duration parsing ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("105ms", 0.105),
    ("1ms", 0.001),
    ("59.16s", 59.16),
    ("8s", 8.0),
    ("1m26.4s", 86.4),
    ("23m2.4s", 1382.4),
    ("2m", 120.0),
    ("1h2m3s", 3723.0),
])
def test_parse_duration_reads_groq_formats(text, expected):
    from phonexi.processor import _parse_duration

    assert _parse_duration(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "soon", None, "abc123"])
def test_parse_duration_rejects_what_it_cannot_read(text):
    from phonexi.processor import _parse_duration

    assert _parse_duration(text) is None


def test_parse_duration_does_not_read_milliseconds_as_minutes():
    from phonexi.processor import _parse_duration

    assert _parse_duration("500ms") < 1


# ── countdown in the message ────────────────────────────────────────────────

def test_message_uses_the_token_reset_header():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_with_headers(
        "on output tokens per minute (OTPM): Limit 1000, Requested 1024.",
        {"x-ratelimit-reset-tokens": "31.44s"},
    )

    assert "32s" in _rate_limit_message(exc)


def test_countdown_rounds_up_so_the_retry_is_never_early():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_with_headers(
        "on tokens per minute (TPM).", {"x-ratelimit-reset-tokens": "8.1s"})

    assert "9s" in _rate_limit_message(exc)


def test_countdown_spells_out_minutes_and_seconds():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_with_headers(
        "on tokens per minute (TPM).", {"x-ratelimit-reset-tokens": "1m26.4s"})
    msg = _rate_limit_message(exc)

    assert "1m 27s" in msg


def test_request_limit_reads_the_request_reset_header():
    """A requests-per-day 429 refills on a different clock than tokens."""
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_with_headers(
        "Rate limit reached: requests per day (RPD).",
        {"x-ratelimit-reset-requests": "23m2.4s", "x-ratelimit-reset-tokens": "1ms"},
    )
    msg = _rate_limit_message(exc)

    assert "23m 3s" in msg


def test_token_error_ignores_the_request_reset_header():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_with_headers(
        "on output tokens per minute (OTPM): Limit 1000, Requested 1024.",
        {"x-ratelimit-reset-requests": "23m2.4s", "x-ratelimit-reset-tokens": "12s"},
    )
    msg = _rate_limit_message(exc)

    assert "12s" in msg
    assert "23m" not in msg


def test_message_falls_back_to_the_body_when_headers_are_missing():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_error("on tokens per minute (TPM). Please try again in 8.5s.")

    assert "8.5s" in _rate_limit_message(exc)


def test_message_stays_vague_when_nothing_says_how_long():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_error("on tokens per minute (TPM).")
    msg = _rate_limit_message(exc)

    assert "Wait about a minute" in msg


def test_a_reset_under_a_second_reads_as_a_second():
    from phonexi.processor import _rate_limit_message

    exc = _rate_limit_with_headers(
        "on tokens per minute (TPM).", {"x-ratelimit-reset-tokens": "105ms"})

    assert "1s" in _rate_limit_message(exc)


def test_message_survives_an_exception_with_no_response():
    from phonexi.processor import _rate_limit_message

    class Bare(Exception):
        pass

    msg = _rate_limit_message(Bare("on tokens per minute (TPM)."))

    assert "Wait about a minute" in msg


# ── retry policy ────────────────────────────────────────────────────────────

def test_client_is_built_without_silent_retries(tmp_path):
    """A retried 429 freezes the popup for the whole reset window.

    The SDK default of 2 turns a 42-second wait into a blank window with no
    explanation. Failing straight away shows the countdown instead.
    """
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.GROQ_MAX_RETRIES", 0), \
         patch("phonexi.processor.Groq", return_value=mock_client) as mock_groq:
        list(process(_png(tmp_path)))

    assert mock_groq.call_args.kwargs["max_retries"] == 0


def test_text_client_is_built_without_silent_retries():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.GROQ_MAX_RETRIES", 0), \
         patch("phonexi.processor.Groq", return_value=mock_client) as mock_groq:
        list(process_text("question"))

    assert mock_groq.call_args.kwargs["max_retries"] == 0


def test_retry_count_is_configurable():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([])

    with patch("phonexi.processor.GROQ_API_KEY", "fake-key"), \
         patch("phonexi.processor.GROQ_MAX_RETRIES", 3), \
         patch("phonexi.processor.Groq", return_value=mock_client) as mock_groq:
        list(process_text("question"))

    assert mock_groq.call_args.kwargs["max_retries"] == 3


def test_default_retry_count_is_zero():
    from phonexi import config

    assert config.GROQ_MAX_RETRIES == 0
