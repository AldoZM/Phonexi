"""Engine interface and the subprocess machinery the CLI engines share.

An engine is whoever answers. The views consume Iterator[str] and never learn
which one it was.
"""

import atexit
import json
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from phonexi.config import PROMPT
from phonexi.processor import BRIEFING_HEADER, Context


# Fastest first: Left/Right in the picker walks this order.
EFFORTS = ("low", "medium", "high")


@dataclass(frozen=True)
class CliChoice:
    """One -cli picker row: a CLI, optionally a model, and its effort level.

    provider/name/capabilities are the shape the picker already draws for
    -model. ids maps each level to the model id it selects; a row with no ids
    lets the CLI pick its model and sends the level as --effort instead.
    """

    provider: str
    name: str
    levels: tuple = ()
    level: str = ""
    ids: tuple = ()

    capabilities = "text, vision"

    @property
    def model_id(self) -> "str | None":
        return dict(self.ids).get(self.level) if self.ids else None


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

    With prewarm, a CLI that can read its prompt from stdin (session_argv) is
    started ahead of time and left waiting: measured 2026-09-22, a fresh agy
    spent 3.8 s of every answer on auth and setup before the model saw the
    question. Each spare answers one question and a new one is started after
    it, so history never piles up — agy read 0 tokens from cache, so a long
    session only makes every turn heavier.
    """

    BINARY = ""
    LABEL = ""

    def __init__(self, prewarm: bool = False) -> None:
        self.prewarm = prewarm
        self._spare: "subprocess.Popen | None" = None
        self._lock = threading.Lock()
        self._atexit = False

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

    def session_argv(self, exe: str) -> "list[str] | None":
        """Flags for a process that takes its prompt on stdin; None if unsupported."""
        return None

    def session_message(self, prompt: str) -> str:
        raise NotImplementedError

    def result_error(self, event: dict) -> "str | None":
        """The failure a terminal event reports, if the CLI reports one there."""
        return None

    # ── the spare process ───────────────────────────────────────────────────

    def _spawn_session(self, exe: str) -> subprocess.Popen:
        return subprocess.Popen(
            self.session_argv(exe),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # A spare idles for minutes; an undrained stderr pipe could fill
            # and stall it. Failures arrive in the result event instead.
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def warm(self) -> None:
        """Start a spare if this engine can use one and none is waiting."""
        if not self.prewarm:
            return
        exe = self._resolve()
        if self.session_argv(exe) is None:
            return
        with self._lock:
            if self._spare is not None and self._spare.poll() is None:
                return
            self._spare = self._spawn_session(exe)
            if not self._atexit:
                # Its stdin closing with Phonexi ends it too; this is the
                # tidy path for a normal exit.
                atexit.register(self.close)
                self._atexit = True

    def close(self) -> None:
        with self._lock:
            spare, self._spare = self._spare, None
        if spare is not None:
            spare.kill()

    def _take_spare(self) -> "subprocess.Popen | None":
        with self._lock:
            spare, self._spare = self._spare, None
        if spare is not None and spare.poll() is None:
            return spare
        return None

    @staticmethod
    def _send(proc: subprocess.Popen, message: str) -> bool:
        try:
            proc.stdin.write(message + "\n")
            proc.stdin.flush()
            # One turn per spare: EOF after the message ends the process.
            proc.stdin.close()
            return True
        except (BrokenPipeError, OSError, ValueError):
            proc.kill()
            return False

    def _session_stream(self, exe: str, prompt: str) -> Iterator[str]:
        message = self.session_message(prompt)
        proc = self._take_spare()
        if proc is None or not self._send(proc, message):
            proc = self._spawn_session(exe)
            if not self._send(proc, message):
                raise EngineError(f"{self.LABEL} ({self.BINARY}): could not start a session")
        # Start the next spare now, while this one answers: warming only after
        # the answer left a question asked 1 s later cold (4.1-4.8 s to the
        # first word against 1.6 s, 2026-09-22).
        self.warm()
        yield from self._read(proc)

    # ── one process per question ────────────────────────────────────────────

    def _stream(self, prompt: str, image: "Path | None" = None) -> Iterator[str]:
        exe = self._resolve()
        if self.prewarm and self.session_argv(exe) is not None:
            yield from self._session_stream(exe, prompt)
            return
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
        yield from self._read(proc)

    def _read(self, proc: subprocess.Popen) -> Iterator[str]:
        produced = False
        reported = None
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
                reported = self.result_error(event) or reported
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
            stderr = ""
            if proc.stderr is not None:
                stderr = proc.stderr.read()
                proc.stderr.close()
            proc.wait()

        if produced:
            return
        if reported:
            raise EngineError(f"{self.LABEL} ({self.BINARY}): {reported}")
        if proc.returncode != 0:
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
