"""Antigravity CLI as the engine.

Measured 2026-09-20 with agy 1.2.7. Two things set it apart from claude: it has
no system-prompt flag, so PROMPT rides in the prompt text, and it has no flag
to restrict tools at all — --sandbox is the only leash it offers.
"""

from pathlib import Path

from phonexi.config import AGY_EFFORT
from phonexi.engines.base import CliEngine, system_prompt


class AgyEngine(CliEngine):
    BINARY = "agy"
    LABEL = "Antigravity"

    def argv(self, exe: str, prompt: str, image: "Path | None") -> list[str]:
        return [
            exe,
            "-p", f"{system_prompt()}\n\n{prompt}",
            "--output-format", "stream-json",
            "--effort", AGY_EFFORT,
            "--sandbox",
        ]

    def extract(self, event: dict) -> str:
        step = event.get("step_update")
        if not isinstance(step, dict):
            return ""
        if step.get("step_type") != "agent_response":
            return ""
        return step.get("text_delta", "") or ""
