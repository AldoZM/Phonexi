"""Which API and which model answer — the catalog behind -model."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from phonexi.config import GEMINI_MODEL, GROQ_MODEL_TEXT, GROQ_MODEL_VISION

GROQ = "groq"
GEMINI = "gemini"

KEY_NAMES = {GROQ: "GROQ_API_KEY", GEMINI: "GEMINI_API_KEY"}
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class Model:
    provider: str
    name: str
    vision: bool
    audio: bool

    @property
    def capabilities(self) -> str:
        caps = ["text"]
        if self.vision:
            caps.append("vision")
        if self.audio:
            caps.append("audio")
        return ", ".join(caps)


@dataclass(frozen=True)
class Selection:
    provider: str
    text_model: str
    vision_model: str


# Kept by hand: the models endpoints list dozens of entries without saying
# which ones read images, and that is the one thing the picker has to show.
CATALOG = [
    Model(GEMINI, "gemini-3.8-flash", vision=True, audio=True),
    Model(GEMINI, "gemini-3.5-flash", vision=True, audio=True),
    Model(GEMINI, "gemini-3.1-flash-lite", vision=True, audio=True),
    Model(GROQ, "openai/gpt-oss-120b", vision=False, audio=False),
    Model(GROQ, "openai/gpt-oss-20b", vision=False, audio=False),
    Model(GROQ, "qwen/qwen3.8-27b", vision=True, audio=False),
]


# Where a busy Gemini request goes next, most stable first. The free tier
# answers 503 under load, and on 2026-09-17 3.8-flash held while the others
# failed or took up to 38 s. gemini-2.5-flash is left out: it is listed by the
# models endpoint but answers 404.
GEMINI_FALLBACK = ["gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash"]


def fallback_for(model: str) -> str:
    """The first Gemini model to retry on that is not the busy one."""
    return next(m for m in GEMINI_FALLBACK if m != model)


def key_order(env_path: Path = ENV_PATH) -> list[str]:
    """Providers with a key, in the order the keys appear in .env.

    The key written highest decides the default provider. Keys that only live
    in the process environment come after, Groq first.
    """
    by_key = {name: provider for provider, name in KEY_NAMES.items()}
    order: list[str] = []
    values = dotenv_values(env_path) if Path(env_path).is_file() else {}
    for name, value in values.items():
        provider = by_key.get(name)
        if provider and value and provider not in order:
            order.append(provider)
    for provider, name in KEY_NAMES.items():
        if provider not in order and os.environ.get(name):
            order.append(provider)
    return order


def available_models(providers: list[str]) -> list[Model]:
    """Catalog models whose provider has a key, grouped in key order."""
    return [m for p in providers for m in CATALOG if m.provider == p]


def find(name: str) -> "Model | None":
    return next((m for m in CATALOG if m.name == name), None)


def selection_for(model: Model) -> Selection:
    """A vision model serves both modes; a text-only one leaves captures on .env."""
    if model.vision:
        return Selection(model.provider, model.name, model.name)
    fallback = GEMINI_MODEL if model.provider == GEMINI else GROQ_MODEL_VISION
    return Selection(model.provider, model.name, fallback)


def default_selection(providers: list[str]) -> Selection:
    """The .env models of the provider whose key is written first."""
    if providers and providers[0] == GEMINI:
        return Selection(GEMINI, GEMINI_MODEL, GEMINI_MODEL)
    return Selection(GROQ, GROQ_MODEL_TEXT, GROQ_MODEL_VISION)


_active = Selection(GROQ, GROQ_MODEL_TEXT, GROQ_MODEL_VISION)


def active() -> Selection:
    return _active


def activate(selection: Selection) -> None:
    global _active
    _active = selection
