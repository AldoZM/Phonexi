"""Antigravity CLI as the engine.

Measured 2026-09-20 with agy 1.2.7. Two things set it apart from claude: it has
no system-prompt flag, so PROMPT rides in the prompt text, and it has no flag
to restrict tools at all — --sandbox is the only leash it offers.

Its effort lives in the model id (gemini-3.8-flash-low/-medium/-high), so the
-cli picker reads `agy models` and turns each family into one row.
"""

import json
import re
import subprocess
from pathlib import Path

from phonexi.config import AGY_EFFORT
from phonexi.engines.base import EFFORTS, CliChoice, CliEngine, system_prompt

# `agy models` fetches the list over the network; past this the picker falls
# back to a single row instead of holding startup hostage.
LIST_TIMEOUT = 10

_LEVEL_SUFFIX = re.compile(r"^(?P<family>.+)-(?P<level>low|medium|high)$")
_LEVEL_LABEL = re.compile(r"\s*\((?:low|medium|high)\)$", re.IGNORECASE)


def _starting_level(levels: tuple, default: str) -> str:
    # high took 17x longer to the first word (bitácora 2026-09-20), so a model
    # without the default starts on its fastest level, not its slowest.
    if default in levels:
        return default
    return levels[0]


def parse_models(output: str, default: str = AGY_EFFORT) -> list[CliChoice]:
    """One picker row per model family, in the order agy lists them."""
    families: dict[str, dict] = {}
    for line in output.splitlines():
        if "\t" not in line:
            continue  # the "Fetching available models..." banner
        model_id, label = (part.strip() for part in line.split("\t", 1))
        if not model_id:
            continue
        match = _LEVEL_SUFFIX.match(model_id)
        if match:
            key, level = match["family"], match["level"]
            label = _LEVEL_LABEL.sub("", label)
        else:
            key, level = model_id, ""
        family = families.setdefault(key, {"label": label, "ids": {}})
        family["ids"][level] = model_id

    rows = []
    for family in families.values():
        ids = family["ids"]
        levels = tuple(l for l in EFFORTS if l in ids)
        if levels:
            rows.append(CliChoice("agy", family["label"], levels,
                                  _starting_level(levels, default),
                                  tuple((l, ids[l]) for l in levels)))
        else:
            rows.append(CliChoice("agy", family["label"], ids=(("", ids[""]),)))
    return rows


def list_models(exe: str) -> list[CliChoice]:
    """Ask agy for its models; any failure means no list, never a crash."""
    try:
        done = subprocess.run(
            [exe, "models"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=LIST_TIMEOUT, stdin=subprocess.DEVNULL,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if done.returncode != 0:
        return []
    return parse_models(done.stdout)


class AgyEngine(CliEngine):
    BINARY = "agy"
    LABEL = "Antigravity"

    def __init__(self, model: "str | None" = None, effort: "str | None" = None,
                 prewarm: bool = False) -> None:
        super().__init__(prewarm)
        self.model = model
        self.effort = effort or AGY_EFFORT

    def _model_flags(self) -> list[str]:
        # A model id already carries its level; sending --effort as well could
        # contradict it.
        if self.model:
            return ["--model", self.model]
        return ["--effort", self.effort]

    def argv(self, exe: str, prompt: str, image: "Path | None") -> list[str]:
        return [
            exe,
            "-p", f"{system_prompt()}\n\n{prompt}",
            "--output-format", "stream-json",
            *self._model_flags(),
            "--sandbox",
        ]

    def session_argv(self, exe: str) -> list[str]:
        # -p goes last and empty: placed before a flag, agy takes that flag as
        # the prompt and refuses to start.
        return [
            exe,
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            *self._model_flags(),
            "--sandbox",
            "-p=",
        ]

    def session_message(self, prompt: str) -> str:
        # Only text blocks are accepted on stdin (checked 2026-09-22: an image
        # block is refused), so a capture still travels as a path to read.
        return json.dumps({
            "event": "user",
            "message": {"role": "user", "content": f"{system_prompt()}\n\n{prompt}"},
        })

    def result_error(self, event: dict) -> "str | None":
        if event.get("event") != "result":
            return None
        result = event.get("result")
        if isinstance(result, dict) and result.get("status") == "ERROR":
            return result.get("error") or "the turn failed"
        return None

    def extract(self, event: dict) -> str:
        step = event.get("step_update")
        if not isinstance(step, dict):
            return ""
        if step.get("step_type") != "agent_response":
            return ""
        return step.get("text_delta", "") or ""
