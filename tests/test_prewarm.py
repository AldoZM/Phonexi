"""The spare process: an agy already started and waiting on stdin.

Measured 2026-09-22: a fresh process per question spent 3.8 s of every answer
on auth and setup before the model saw the question. A spare started ahead of
time cut the first word from 4.8-6.5 s to 1.2-1.6 s, and still answered after
waiting 6 minutes idle.
"""

import json

import pytest

from phonexi import engines
from phonexi.engines import EngineError, engine_for
from phonexi.engines.agy import AgyEngine
from phonexi.engines.base import EFFORTS, CliChoice
from phonexi.engines.claude import ClaudeEngine


def agy_lines(*texts, error=None):
    out = [json.dumps({"event": "init", "conversation_id": "c1"})]
    for t in texts:
        out.append(json.dumps({"event": "step_update", "step_update": {
            "step_type": "agent_response", "text_delta": t}}))
    result = {"status": "ERROR", "error": error} if error else {"status": "SUCCESS"}
    out.append(json.dumps({"event": "result", "result": result}))
    return out


class FakeStdin:
    def __init__(self, broken=False):
        self.written = []
        self.closed = False
        self.broken = broken

    def write(self, text):
        if self.broken:
            raise BrokenPipeError("spare died")
        self.written.append(text)

    def flush(self):
        pass

    def close(self):
        self.closed = True


class FakeSession:
    """A spawned agy waiting on stdin; answers once its stdin is closed."""

    def __init__(self, argv, lines, exited=None, broken=False, returncode=0):
        self.argv = argv
        self.stdin = FakeStdin(broken)
        self._lines = lines
        self._exited = exited
        self.returncode = returncode
        self.stderr = None
        self.killed = False

    @property
    def stdout(self):
        return iter(line + "\n" for line in self._lines)

    def poll(self):
        return self._exited

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True

    def sent(self):
        return [json.loads(line) for line in "".join(self.stdin.written).splitlines()]


@pytest.fixture
def spawner(monkeypatch):
    """Record every Popen; each new process answers with the next script."""
    state = {"procs": [], "scripts": [], "default": agy_lines("answer")}
    monkeypatch.setattr(engines.base.shutil, "which", lambda name: "C:/fake/agy.exe")

    def popen(argv, **kwargs):
        script = state["scripts"].pop(0) if state["scripts"] else {}
        proc = FakeSession(argv, script.get("lines", state["default"]),
                           exited=script.get("exited"), broken=script.get("broken", False))
        proc.kwargs = kwargs
        state["procs"].append(proc)
        return proc

    monkeypatch.setattr(engines.base.subprocess, "Popen", popen)
    return state


def test_warm_starts_one_waiting_process(spawner):
    engine = AgyEngine(prewarm=True)
    engine.warm()
    assert len(spawner["procs"]) == 1
    argv = spawner["procs"][0].argv
    assert argv[argv.index("--input-format") + 1] == "stream-json"
    assert argv[-1] == "-p="  # -p before a flag would swallow the flag as its prompt


def test_warm_twice_keeps_a_single_spare(spawner):
    engine = AgyEngine(prewarm=True)
    engine.warm()
    engine.warm()
    assert len(spawner["procs"]) == 1


def test_the_question_goes_to_the_spare_over_stdin(spawner):
    engine = AgyEngine(prewarm=True)
    engine.warm()
    spare = spawner["procs"][0]
    assert "".join(engine.answer_text("why a pool?")) == "answer"
    message = spare.sent()[0]
    assert message["event"] == "user"
    assert message["message"]["role"] == "user"
    assert "why a pool?" in message["message"]["content"]
    assert spare.stdin.closed, "one turn per spare: closing stdin ends it"


def test_the_prompt_rides_in_the_message_because_agy_has_no_system_flag(spawner):
    from phonexi.engines.base import system_prompt
    engine = AgyEngine(prewarm=True)
    list(engine.answer_text("why?"))
    content = spawner["procs"][0].sent()[0]["message"]["content"]
    assert content.startswith(system_prompt(voice=True))


def test_a_new_spare_is_started_after_each_answer(spawner):
    engine = AgyEngine(prewarm=True)
    engine.warm()
    list(engine.answer_text("q1"))
    assert len(spawner["procs"]) == 2
    list(engine.answer_text("q2"))
    assert len(spawner["procs"]) == 3
    assert spawner["procs"][1].sent(), "the second question must use the second spare"


def test_the_next_spare_starts_as_soon_as_the_question_is_sent(spawner):
    # Warming only after the answer left a 1 s gap between questions cold:
    # 4.1 and 4.8 s to the first word instead of 1.6 s (2026-09-22).
    engine = AgyEngine(prewarm=True)
    engine.warm()
    stream = engine.answer_text("q1")
    next(stream)
    assert len(spawner["procs"]) == 2, "the next spare must be warming while this answer streams"
    list(stream)
    assert len(spawner["procs"]) == 2, "finishing the answer must not start a third"


def test_without_warm_the_first_question_starts_its_own_session(spawner):
    engine = AgyEngine(prewarm=True)
    assert "".join(engine.answer_text("why?")) == "answer"
    assert spawner["procs"][0].sent()


def test_a_dead_spare_is_replaced_not_written_to(spawner):
    spawner["scripts"] = [{"exited": 1}]
    engine = AgyEngine(prewarm=True)
    engine.warm()
    dead = spawner["procs"][0]
    assert "".join(engine.answer_text("why?")) == "answer"
    assert not dead.stdin.written
    assert spawner["procs"][1].sent()


def test_a_broken_pipe_falls_back_to_a_fresh_process(spawner):
    spawner["scripts"] = [{"broken": True}]
    engine = AgyEngine(prewarm=True)
    engine.warm()
    broken = spawner["procs"][0]
    assert "".join(engine.answer_text("why?")) == "answer"
    assert broken.killed
    assert spawner["procs"][1].sent()


def test_an_error_result_becomes_a_readable_error(spawner):
    spawner["default"] = agy_lines(error="quota exhausted")
    engine = AgyEngine(prewarm=True)
    with pytest.raises(EngineError) as exc:
        list(engine.answer_text("why?"))
    assert "quota exhausted" in str(exc.value)


def test_the_spare_keeps_the_chosen_model(spawner):
    engine = AgyEngine(model="gemini-3.8-flash-low", prewarm=True)
    engine.warm()
    argv = spawner["procs"][0].argv
    assert argv[argv.index("--model") + 1] == "gemini-3.8-flash-low"
    assert "--sandbox" in argv


def test_close_kills_the_waiting_spare(spawner):
    engine = AgyEngine(prewarm=True)
    engine.warm()
    engine.close()
    assert spawner["procs"][0].killed


def test_a_view_closing_early_kills_the_answering_process(spawner):
    spawner["default"] = agy_lines("a", "b", "c")
    engine = AgyEngine(prewarm=True)
    stream = engine.answer_text("why?")
    next(stream)
    stream.close()
    assert spawner["procs"][0].killed


def test_without_prewarm_agy_still_takes_the_prompt_on_the_command_line(spawner):
    engine = AgyEngine()
    list(engine.answer_text("why?"))
    argv = spawner["procs"][0].argv
    assert "--input-format" not in argv
    assert "why?" in argv[argv.index("-p") + 1]


def test_claude_has_no_spare_and_keeps_its_one_shot_process(spawner):
    engine = ClaudeEngine()
    engine.warm()  # a no-op, so main can warm whatever engine it built
    assert spawner["procs"] == []


def test_engine_for_turns_prewarm_on_for_agy(monkeypatch):
    monkeypatch.setattr(engines, "CLI_PREWARM", True)
    row = CliChoice("agy", "Gemini 3.8 Flash", EFFORTS, "low",
                    tuple((l, f"gemini-3.8-flash-{l}") for l in EFFORTS))
    assert engine_for(row).prewarm is True


def test_cli_prewarm_off_restores_the_old_behaviour(monkeypatch):
    monkeypatch.setattr(engines, "CLI_PREWARM", False)
    row = CliChoice("agy", "Antigravity", EFFORTS, "low")
    assert engine_for(row).prewarm is False


def test_a_prewarmed_capture_carries_the_capture_prompt(spawner, tmp_path):
    from phonexi.config import PROMPT_CAPTURE
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    list(AgyEngine(prewarm=True).answer_image(shot))
    content = spawner["procs"][0].sent()[0]["message"]["content"]
    assert content.startswith(PROMPT_CAPTURE)
