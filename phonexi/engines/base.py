"""Engine interface and the subprocess machinery the CLI engines share.

An engine is whoever answers. The views consume Iterator[str] and never learn
which one it was.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterator, Protocol

from phonexi.config import PROMPT
from phonexi.processor import BRIEFING_HEADER, Context


class EngineNotConfiguredError(Exception):
    """The engine cannot run at all: no API key, or the CLI is not installed."""


class EngineError(Exception):
    """The engine failed while answering."""


class Engine(Protocol):
    def answer_image(self, path: Path, briefing: "str | None" = None) -> Iterator[str]: ...

    def answer_text(
        self,
        question: str,
        context: "Context | None" = None,
        briefing: "str | None" = None,
    ) -> Iterator[str]: ...


IMAGE_INSTRUCTION = (
    "Read the image at {path}. It is a screenshot of an interview question. "
    "Answer the question it shows. Open the file straight away: do not announce "
    "the tool call and do not narrate what you are about to do. The first "
    "characters you output must be the answer itself."
)


def _compose(question: str, context: "Context | None", briefing: "str | None") -> str:
    """Fold briefing and history into one prompt.

    Every question launches a fresh process, so nothing survives between calls.
    The CLIs have --continue, but Context is kept so both engines behave alike.
    """
    parts: list[str] = []
    if briefing and briefing.strip():
        parts.append(BRIEFING_HEADER + briefing.strip())
    if context is not None:
        parts.append(f"Earlier in this conversation:\nQ: {context.user_turn}\n"
                     f"A: {context.assistant_turn}")
    parts.append(question)
    return "\n\n".join(parts)


_SHIM_SUFFIXES = (".cmd", ".bat")
_SHIM_TARGET = re.compile(r'"([^"]*\.exe)"', re.IGNORECASE)


def _real_executable(path: str) -> str:
    """Follow an npm .CMD shim to the .exe it wraps.

    A .CMD runs through cmd.exe, which cuts the command at the first newline.
    PROMPT has 13 of them and the briefing has more, so every flag after the
    break was silently dropped — stream-json among them, which turned the
    answer back into plain text. Calling the .exe skips cmd.exe entirely.
    """
    if not path.lower().endswith(_SHIM_SUFFIXES):
        return path
    try:
        script = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path
    here = str(Path(path).parent)
    for match in _SHIM_TARGET.finditer(script):
        target = Path(match.group(1).replace("%dp0%", here).replace("%~dp0", here))
        if target.is_file():
            return str(target)
    return path


class CliEngine:
    """Launch a local CLI, read its NDJSON, yield text as it arrives.

    Subclasses supply the flags (argv) and where the text sits (extract).
    """

    BINARY = ""
    LABEL = ""

    def _resolve(self) -> str:
        # On Windows `claude` is an npm .CMD, not an .exe: Popen(["claude"])
        # dies with WinError 2. which() finds the real one.
        exe = shutil.which(self.BINARY)
        if exe is None:
            raise EngineNotConfiguredError(
                f"{self.BINARY} is not installed or not on PATH — "
                f"install {self.LABEL} or run without -cli."
            )
        return _real_executable(exe)

    def argv(self, exe: str, prompt: str, image: "Path | None") -> list[str]:
        raise NotImplementedError

    def extract(self, event: dict) -> str:
        raise NotImplementedError

    def _stream(self, prompt: str, image: "Path | None" = None) -> Iterator[str]:
        exe = self._resolve()
        proc = subprocess.Popen(
            self.argv(exe, prompt, image),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            # claude waits 3s for stdin it will never get; closing it here is
            # worth ~3s off the first token.
            stdin=subprocess.DEVNULL,
        )
        produced = False
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    # A stray non-JSON line is noise, not a reason to stop.
                    continue
                if not isinstance(event, dict):
                    continue
                token = self.extract(event)
                if token:
                    produced = True
                    yield token
        except GeneratorExit:
            # The view closed early — do not leave the CLI running.
            proc.kill()
            raise
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            stderr = proc.stderr.read()
            proc.stderr.close()
            proc.wait()

        if proc.returncode != 0 and not produced:
            detail = stderr.strip().splitlines()
            message = detail[-1] if detail else f"exited with code {proc.returncode}"
            raise EngineError(f"{self.LABEL} ({self.BINARY}): {message}")

    # ── the Engine interface ────────────────────────────────────────────────

    def answer_text(
        self,
        question: str,
        context: "Context | None" = None,
        briefing: "str | None" = None,
    ) -> Iterator[str]:
        yield from self._stream(_compose(question, context, briefing))

    def answer_image(self, path: Path, briefing: "str | None" = None) -> Iterator[str]:
        question = IMAGE_INSTRUCTION.format(path=path)
        yield from self._stream(_compose(question, None, briefing), image=Path(path))


def system_prompt() -> str:
    return PROMPT
