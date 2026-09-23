"""Which engine answers — the catalog behind -cli."""

from phonexi.config import CLI_PREWARM
from phonexi.engines import agy, base
from phonexi.engines.agy import AgyEngine
from phonexi.engines.api import ApiEngine
from phonexi.engines.base import (
    EFFORTS,
    CliChoice,
    Engine,
    EngineError,
    EngineNotConfiguredError,
)
from phonexi.engines.claude import ClaudeEngine

CLI = "cli"

# Picker order: agy's models first, since it is the one with a model list.
ENGINES = {
    "agy": AgyEngine,
    "claude": ClaudeEngine,
}

# claude had no --effort before the picker; medium matches agy's default.
CLAUDE_START_LEVEL = "medium"


def get_engine(name: str, **options) -> Engine:
    """Build the CLI engine called name, or raise KeyError."""
    return ENGINES[name](**options)


def engine_for(choice: CliChoice) -> Engine:
    """The engine a picker row stands for, with its model and level applied."""
    if choice.provider == "agy":
        if choice.model_id:
            return AgyEngine(model=choice.model_id, prewarm=CLI_PREWARM)
        return AgyEngine(effort=choice.level or None, prewarm=CLI_PREWARM)
    return get_engine(choice.provider, effort=choice.level or None, prewarm=CLI_PREWARM)


def installed() -> list[CliChoice]:
    """Picker rows for the CLIs actually on this machine.

    agy contributes one row per model family from `agy models`; if that list
    cannot be read it shrinks to a single row that lets agy pick the model.
    Neither CLI reads audio, so the voice flow keeps Groq Whisper.
    """
    rows: list[CliChoice] = []
    exe = base.shutil.which(AgyEngine.BINARY)
    if exe is not None:
        models = agy.list_models(base._real_executable(exe))
        rows += models or [
            CliChoice("agy", AgyEngine.LABEL, EFFORTS, agy._starting_level(EFFORTS, agy.AGY_EFFORT))
        ]
    if base.shutil.which(ClaudeEngine.BINARY) is not None:
        rows.append(CliChoice("claude", ClaudeEngine.LABEL, EFFORTS, CLAUDE_START_LEVEL))
    return rows


__all__ = [
    "ApiEngine",
    "CLI",
    "CliChoice",
    "Engine",
    "EngineError",
    "EngineNotConfiguredError",
    "engine_for",
    "get_engine",
    "installed",
]
