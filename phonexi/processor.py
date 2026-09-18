import base64
import math
import re
from pathlib import Path
from typing import Iterator

from groq import BadRequestError, Groq, RateLimitError

from phonexi.config import (
    GROQ_API_KEY,
    GROQ_MAX_RETRIES,
    GROQ_MAX_TOKENS,
    GROQ_MODEL_TEXT,
    GROQ_MODEL_VISION,
    GROQ_REASONING_TEXT,
    GROQ_REASONING_VISION,
    PROMPT,
)
from phonexi.relevance import select


class GroqNotConfiguredError(Exception):
    pass


class GroqAPIError(Exception):
    pass


BRIEFING_HEADER = (
    "Background about the candidate (stack, role, experience). Treat it as your own "
    "knowledge and answer straight from it. It is NOT the question, so never answer "
    "it directly. Never mention, quote, or allude to this background as a source: no "
    "'based on the context', no 'according to your document', no 'as you mentioned'. "
    "The reply is spoken aloud in an interview — it must sound like the candidate "
    "recalling their own work, and it must open with the answer itself:\n"
)


def _briefing_message(
    briefing: "str | None",
    question: "str | None" = None,
) -> "dict | None":
    """Wrap the briefing as a system message.

    With a question, only the sections that answer it are sent — the whole
    ficha on every call is what exhausts the tokens-per-minute allowance.
    """
    if not briefing or not briefing.strip():
        return None
    text = briefing.strip()
    if question is not None:
        text = select(text, question)
    return {"role": "system", "content": BRIEFING_HEADER + text}


# Groq spells a reset as "105ms", "59.16s", "1m26.4s", "23m2.4s". Milliseconds
# must match before minutes or "500ms" reads as 500 minutes.
_DURATION_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)")
_SECONDS_PER = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def _parse_duration(text: "str | None") -> "float | None":
    """Read a Groq reset value into seconds, or None if it says nothing."""
    if not text:
        return None
    parts = _DURATION_UNIT.findall(text)
    if not parts:
        return None
    return sum(float(value) * _SECONDS_PER[unit] for value, unit in parts)


def _format_wait(seconds: float) -> str:
    """Round up — telling someone to retry early just earns a second 429."""
    total = max(1, math.ceil(seconds))
    if total < 60:
        return f"{total}s"
    return f"{total // 60}m {total % 60}s"


def _reset_header(exc: Exception, name: str) -> "str | None":
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is None:
        return None
    try:
        return headers.get(name)
    except AttributeError:
        return None


def _rate_limit_message(exc: Exception) -> str:
    """Turn Groq's raw 429 JSON into one line the popup can show.

    The raw error is a wall of JSON that buries the two things worth knowing:
    which allowance ran out and how long until it refills. The countdown comes
    from the response headers, which carry it even when the message body does
    not — the OTPM refusal never mentions a delay anywhere in its text.
    """
    raw = str(exc)
    if "output tokens per minute" in raw:
        what = "the answer-length allowance for this minute is used up"
        header = "x-ratelimit-reset-tokens"
    elif "tokens per minute" in raw:
        what = "the tokens-per-minute allowance is used up"
        header = "x-ratelimit-reset-tokens"
    elif "tokens per day" in raw:
        what = "the tokens-per-day allowance is used up"
        header = "x-ratelimit-reset-tokens"
    elif "requests per" in raw:
        what = "too many requests in a row"
        header = "x-ratelimit-reset-requests"
    else:
        what = "the account hit a Groq rate limit"
        header = "x-ratelimit-reset-tokens"

    seconds = _parse_duration(_reset_header(exc, header))
    if seconds is not None:
        tail = f" Retry in {_format_wait(seconds)}."
    else:
        body = re.search(r"try again in ([\d.]+\s*[a-z]+(?:[\d.]+\s*[a-z]+)?)", raw)
        tail = f" Retry in {body.group(1)}." if body else " Wait about a minute."
    return "Groq: " + what + "." + tail


def _client() -> Groq:
    """Build the API client with retries under our control, not the SDK's."""
    return Groq(api_key=GROQ_API_KEY, max_retries=GROQ_MAX_RETRIES)


def _open_stream(client: Groq, reasoning_effort: str, **kwargs):
    """Open the stream, dropping reasoning_effort if this model rejects it.

    Each model family names the levels differently, so a model swap in .env
    would otherwise turn into a hard 400 on the next hotkey press.
    """
    if reasoning_effort:
        try:
            return client.chat.completions.create(
                stream=True, reasoning_effort=reasoning_effort, **kwargs
            )
        except BadRequestError as exc:
            if "reasoning_effort" not in str(exc):
                raise
    return client.chat.completions.create(stream=True, **kwargs)


def _stream_tokens(client: Groq, reasoning_effort: str = "", **kwargs) -> Iterator[str]:
    """Yield content tokens, collapsing a 429 into a readable GroqAPIError."""
    try:
        stream = _open_stream(client, reasoning_effort, **kwargs)
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token
    except RateLimitError as exc:
        raise GroqAPIError(_rate_limit_message(exc)) from exc


class Context:
    """Last exchange kept so follow-up questions have conversation history."""
    def __init__(self, user_turn: str, assistant_turn: str) -> None:
        self.user_turn = user_turn
        self.assistant_turn = assistant_turn


def process_text(
    question: str,
    context: "Context | None" = None,
    briefing: "str | None" = None,
) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    client = _client()
    messages: list[dict] = [{"role": "system", "content": PROMPT}]

    brief_msg = _briefing_message(briefing, question)
    if brief_msg is not None:
        messages.append(brief_msg)

    if context is not None:
        messages.append({"role": "user",      "content": context.user_turn})
        messages.append({"role": "assistant", "content": context.assistant_turn})

    messages.append({"role": "user", "content": question})

    yield from _stream_tokens(
        client,
        model=GROQ_MODEL_TEXT,
        messages=messages,
        max_tokens=GROQ_MAX_TOKENS,
        reasoning_effort=GROQ_REASONING_TEXT,
    )


def process(path: Path, briefing: "str | None" = None) -> Iterator[str]:
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY not set")

    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    client = _client()

    messages: list[dict] = []

    brief_msg = _briefing_message(briefing)
    if brief_msg is not None:
        messages.append(brief_msg)

    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
                {"type": "text", "text": PROMPT},
            ],
        }
    )

    yield from _stream_tokens(
        client,
        model=GROQ_MODEL_VISION,
        messages=messages,
        max_tokens=GROQ_MAX_TOKENS,
        reasoning_effort=GROQ_REASONING_VISION,
    )
