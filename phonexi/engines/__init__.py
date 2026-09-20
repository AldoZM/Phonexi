"""Which engine answers — the catalog behind -cli."""

import shutil

from phonexi.engines import base
from phonexi.engines.agy import AgyEngine
from phonexi.engines.api import ApiEngine
from phonexi.engines.base import Engine, EngineError, EngineNotConfiguredError
from phonexi.engines.claude import ClaudeEngine
from phonexi.providers import Model

CLI = "cli"

ENGINES = {
    "claude": ClaudeEngine,
    "agy": AgyEngine,
}


def get_engine(name: str) -> Engine:
    """Build the CLI engine called name, or raise KeyError."""
    return ENGINES[name]()


def installed() -> list[Model]:
    """The CLIs actually on this machine, shaped for the -model picker.

    Neither reads audio: claude says so outright and agy goes off investigating
    the file instead of transcribing it, so the voice flow keeps Groq Whisper.
    """
    return [
        Model(CLI, name, vision=True, audio=False)
        for name, engine in ENGINES.items()
        if base.shutil.which(engine.BINARY) is not None
    ]


__all__ = [
    "ApiEngine",
    "CLI",
    "Engine",
    "EngineError",
    "EngineNotConfiguredError",
    "get_engine",
    "installed",
]
