"""Claude Code as the engine.

Measured 2026-09-20 with claude 2.1.278: --include-partial-messages is what
turns stream-json into an actual stream. Without it the whole answer arrives
in one assistant event at the end.
"""

from pathlib import Path

from phonexi.engines.base import CliEngine, system_prompt


class ClaudeEngine(CliEngine):
    BINARY = "claude"
    LABEL = "Claude Code"

    def __init__(self, effort: "str | None" = None, prewarm: bool = False) -> None:
        # No session_argv yet, so prewarm is accepted and has no effect.
        super().__init__(prewarm)
        # None leaves claude on its own default, which is what -cli sent
        # before the picker had levels.
        self.effort = effort

    def argv(self, exe: str, prompt: str, image: "Path | None") -> list[str]:
        args = [
            exe,
            "-p", prompt,
            "--system-prompt", system_prompt(),
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            # It is an agent: without a leash it can go exploring mid-interview.
            # Reading the screenshot is the only tool it ever needs.
            "--allowed-tools", "Read" if image else "",
        ]
        if self.effort:
            args += ["--effort", self.effort]
        if image is not None:
            # It refuses to read outside its working directory, and Phonexi may
            # well be launched from somewhere else entirely.
            args += ["--add-dir", str(Path(image).parent)]
        return args

    def extract(self, event: dict) -> str:
        if event.get("type") != "stream_event":
            return ""
        inner = event.get("event")
        if not isinstance(inner, dict) or inner.get("type") != "content_block_delta":
            return ""
        delta = inner.get("delta")
        if not isinstance(delta, dict):
            return ""
        return delta.get("text", "") or ""
