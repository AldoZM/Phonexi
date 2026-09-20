import base64
import math
import re
from pathlib import Path
from typing import Iterator

import groq
import openai
from groq import Groq
from openai import OpenAI

from phonexi import providers
from phonexi.config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MAX_TOKENS,
    GEMINI_REASONING,
    GROQ_API_KEY,
    GROQ_MAX_RETRIES,
    GROQ_MAX_TOKENS,
    GROQ_REASONING_TEXT,
    GROQ_REASONING_VISION,
    PROMPT,
)
from phonexi.relevance import select

# Both SDKs share the OpenAI error shapes but define their own classes.
_BAD_REQUEST = (groq.BadRequestError, openai.BadRequestError)
_SERVER_ERROR = (groq.InternalServerError, openai.InternalServerError)

# Groq names the field in its 400; Gemini only names the level it refused.
_REASONING_REJECTED = ("reasoning_effort", "Thinking level")


class GroqNotConfiguredError(Exception):
    """The active provider has no API key; key_name says which one to set."""

    def __init__(self, key_name: str = "GROQ_API_KEY") -> None:
        super().__init__(f"{key_name} not set")
        self.key_name = key_name


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


def _gemini_rate_limit_message(exc: Exception) -> str:
    """Gemini's 429 is a RESOURCE_EXHAUSTED JSON; keep only what ran out and the wait."""
    raw = str(exc)
    what = ("the daily quota is used up" if "PerDay" in raw
            else "the per-minute quota is used up")
    # Retry-After is plain seconds with no unit, unlike Groq's reset headers.
    header = _reset_header(exc, "retry-after")
    seconds = float(header) if header and header.replace(".", "", 1).isdigit() else None
    if seconds is None:
        body = re.search(r'retry(?:Delay"?:\s*"| in )([\d.]+)s', raw, re.IGNORECASE)
        seconds = float(body.group(1)) if body else None
    tail = f" Retry in {_format_wait(seconds)}." if seconds is not None else " Wait about a minute."
    return "Gemini: " + what + "." + tail


def _require_key() -> str:
    """The active provider's key, or the error that names the variable to set."""
    if providers.active().provider == providers.GEMINI:
        if not GEMINI_API_KEY:
            raise GroqNotConfiguredError("GEMINI_API_KEY")
        return GEMINI_API_KEY
    if not GROQ_API_KEY:
        raise GroqNotConfiguredError("GROQ_API_KEY")
    return GROQ_API_KEY


def _client():
    """Build the API client with retries under our control, not the SDK's."""
    key = _require_key()
    if providers.active().provider == providers.GEMINI:
        return OpenAI(api_key=key, base_url=GEMINI_BASE_URL, max_retries=GROQ_MAX_RETRIES)
    return Groq(api_key=key, max_retries=GROQ_MAX_RETRIES)


def _limits(vision: bool) -> tuple[int, str]:
    """Answer cap and reasoning level for the active provider and mode."""
    if providers.active().provider == providers.GEMINI:
        return GEMINI_MAX_TOKENS, GEMINI_REASONING
    return GROQ_MAX_TOKENS, (GROQ_REASONING_VISION if vision else GROQ_REASONING_TEXT)


def _open_stream(client, reasoning_effort: str, **kwargs):
    """Open the stream, dropping reasoning_effort if this model rejects it.

    Each model family names the levels differently, so a model swap in .env
    would otherwise turn into a hard 400 on the next hotkey press.
    """
    if reasoning_effort:
        try:
            return client.chat.completions.create(
                stream=True, reasoning_effort=reasoning_effort, **kwargs
            )
        except _BAD_REQUEST as exc:
            if not any(marker in str(exc) for marker in _REASONING_REJECTED):
                raise
    return client.chat.completions.create(stream=True, **kwargs)


def _stream_tokens(client, reasoning_effort: str = "", **kwargs) -> Iterator[str]:
    """Yield content tokens, collapsing a 429 into a readable GroqAPIError."""
    try:
        try:
            stream = _open_stream(client, reasoning_effort, **kwargs)
        except _SERVER_ERROR as exc:
            # One retry on another Gemini model: the free tier's 503 is per
            # model, and a lost question mid-interview costs more than a switch.
            if (getattr(exc, "status_code", None) != 503
                    or providers.active().provider != providers.GEMINI):
                raise
            busy = kwargs["model"]
            kwargs["model"] = providers.fallback_for(busy)
            stream = _open_stream(client, reasoning_effort, **kwargs)
            yield f"[{busy} was overloaded; answered by {kwargs['model']}]\n\n"
        for chunk in stream:
            if not chunk.choices:
                continue
            token = chunk.choices[0].delta.content
            if token:
                yield token
    except groq.RateLimitError as exc:
        raise GroqAPIError(_rate_limit_message(exc)) from exc
    except openai.RateLimitError as exc:
        raise GroqAPIError(_gemini_rate_limit_message(exc)) from exc
    except _SERVER_ERROR as exc:
        # A 503 is a busy model, not a broken request — say so instead of the JSON.
        if getattr(exc, "status_code", None) != 503:
            raise
        name = "Gemini" if providers.active().provider == providers.GEMINI else "Groq"
        raise GroqAPIError(
            f"{name}: the model is overloaded right now. Try again in a moment "
            "or start with -model to pick another."
        ) from exc


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
    client = _client()
    max_tokens, reasoning = _limits(vision=False)
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
        model=providers.active().text_model,
        messages=messages,
        max_tokens=max_tokens,
        reasoning_effort=reasoning,
    )


def process(path: Path, briefing: "str | None" = None) -> Iterator[str]:
    client = _client()
    max_tokens, reasoning = _limits(vision=True)
    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")

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
        model=providers.active().vision_model,
        messages=messages,
        max_tokens=max_tokens,
        reasoning_effort=reasoning,
    )
