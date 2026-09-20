import json
import subprocess

import pytest

from phonexi import engines
from phonexi.engines import EngineError, EngineNotConfiguredError, get_engine, installed
from phonexi.engines.agy import AgyEngine
from phonexi.engines.claude import ClaudeEngine
from phonexi.processor import Context


# ── fake subprocess ─────────────────────────────────────────────────────────

class FakeProc:
    """Stands in for Popen: hands back canned NDJSON lines."""

    def __init__(self, lines, returncode=0, stderr=""):
        self.stdout = iter(line + "\n" for line in lines)
        self.stderr = _FakeStderr(stderr)
        self.returncode = returncode
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True


class _FakeStderr:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text

    def close(self):
        pass


def fake_popen(lines, returncode=0, stderr="", record=None):
    def _popen(argv, **kwargs):
        if record is not None:
            record["argv"] = argv
            record["kwargs"] = kwargs
        return FakeProc(lines, returncode, stderr)
    return _popen


def claude_lines(*texts):
    out = [json.dumps({"type": "system", "subtype": "init"})]
    for t in texts:
        out.append(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": t}},
        }))
    out.append(json.dumps({"type": "result", "subtype": "success"}))
    return out


def agy_lines(*texts):
    out = [json.dumps({"event": "init", "init": {"cwd": "."}})]
    for t in texts:
        out.append(json.dumps({
            "event": "step_update",
            "step_update": {"step_type": "agent_response", "text_delta": t},
        }))
    out.append(json.dumps({"event": "result", "result": {"status": "SUCCESS"}}))
    return out


@pytest.fixture
def wired(monkeypatch):
    """Patch which() and Popen; return the dict that captures the call."""
    record = {}

    def _wire(lines, returncode=0, stderr="", exe="C:/fake/cli.exe"):
        monkeypatch.setattr(engines.base.shutil, "which", lambda name: exe)
        monkeypatch.setattr(
            engines.base.subprocess, "Popen",
            fake_popen(lines, returncode, stderr, record),
        )
        return record

    return _wire


# ── streaming: each CLI has its own NDJSON shape ────────────────────────────

def test_claude_yields_content_block_deltas(wired):
    wired(claude_lines("Use a ", "connection ", "pool."))
    assert "".join(ClaudeEngine().answer_text("why?")) == "Use a connection pool."


def test_agy_yields_step_update_text_deltas(wired):
    wired(agy_lines("Use a ", "connection ", "pool."))
    assert "".join(AgyEngine().answer_text("why?")) == "Use a connection pool."


def test_claude_ignores_agy_shaped_events(wired):
    wired(agy_lines("ignored"))
    assert "".join(ClaudeEngine().answer_text("why?")) == ""


def test_agy_ignores_claude_shaped_events(wired):
    wired(claude_lines("ignored"))
    assert "".join(AgyEngine().answer_text("why?")) == ""


def test_agy_skips_tool_steps(wired):
    lines = [json.dumps({
        "event": "step_update",
        "step_update": {"step_type": "tool", "text_delta": "reading file"},
    })] + agy_lines("answer")
    wired(lines)
    assert "".join(AgyEngine().answer_text("why?")) == "answer"


def test_tokens_arrive_before_the_process_ends(wired):
    """The view must be able to paint the first token without waiting."""
    wired(claude_lines("first", "second"))
    stream = ClaudeEngine().answer_text("why?")
    assert next(stream) == "first"


def test_a_malformed_line_does_not_kill_the_stream(wired):
    lines = ["not json at all"] + claude_lines("still here")
    wired(lines)
    assert "".join(ClaudeEngine().answer_text("why?")) == "still here"


# ── the flags the spike proved mandatory ────────────────────────────────────

def test_claude_asks_for_partial_messages(wired):
    """Without this flag claude delivers one block at the end, not a stream."""
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?"))
    assert "--include-partial-messages" in record["argv"]


def test_stdin_is_closed_so_claude_does_not_wait_for_it(wired):
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?"))
    assert record["kwargs"]["stdin"] is subprocess.DEVNULL


def test_the_binary_is_resolved_with_which(wired):
    """Bare "claude" is a .CMD on Windows and Popen fails with WinError 2."""
    record = wired(claude_lines("hi"), exe="C:/resolved/claude.CMD")
    list(ClaudeEngine().answer_text("why?"))
    assert record["argv"][0] == "C:/resolved/claude.CMD"


def test_claude_carries_the_prompt_as_a_system_prompt(wired):
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?"))
    argv = record["argv"]
    assert "--system-prompt" in argv
    assert argv[argv.index("--system-prompt") + 1].strip()


def test_agy_prepends_the_prompt_because_it_has_no_system_flag(wired):
    record = wired(agy_lines("hi"))
    list(AgyEngine().answer_text("why is the sky blue?"))
    argv = record["argv"]
    assert "--system-prompt" not in argv
    sent = argv[argv.index("-p") + 1]
    assert sent.endswith("why is the sky blue?")
    assert len(sent) > len("why is the sky blue?")


def test_agy_runs_sandboxed(wired):
    record = wired(agy_lines("hi"))
    list(AgyEngine().answer_text("why?"))
    assert "--sandbox" in record["argv"]


# ── tool leash: text mode must not let the agent wander ─────────────────────

def test_claude_text_mode_allows_no_tools(wired):
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?"))
    argv = record["argv"]
    assert argv[argv.index("--allowed-tools") + 1] == ""


def test_claude_image_mode_allows_only_read(wired, tmp_path):
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_image(shot))
    argv = record["argv"]
    assert argv[argv.index("--allowed-tools") + 1] == "Read"


def test_image_path_is_handed_over_not_the_bytes(wired, tmp_path):
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_image(shot))
    assert str(shot) in record["argv"][record["argv"].index("-p") + 1]


# ── briefing and follow-up context ──────────────────────────────────────────

def test_briefing_reaches_the_cli(wired):
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?", briefing="Aldo ships Flutter apps."))
    assert "Aldo ships Flutter apps." in " ".join(record["argv"])


def test_context_reaches_the_cli(wired):
    record = wired(claude_lines("hi"))
    ctx = Context(user_turn="what is a mutex?", assistant_turn="a lock.")
    list(ClaudeEngine().answer_text("and a semaphore?", context=ctx))
    sent = record["argv"][record["argv"].index("-p") + 1]
    assert "what is a mutex?" in sent
    assert "a lock." in sent


def test_an_empty_briefing_adds_nothing(wired):
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?", briefing="   "))
    sent = record["argv"][record["argv"].index("-p") + 1]
    assert sent == "why?"


# ── failures ────────────────────────────────────────────────────────────────

def test_a_missing_cli_is_reported_before_anything_runs(monkeypatch):
    monkeypatch.setattr(engines.base.shutil, "which", lambda name: None)
    with pytest.raises(EngineNotConfiguredError) as exc:
        list(ClaudeEngine().answer_text("why?"))
    assert "claude" in str(exc.value)


def test_a_nonzero_exit_becomes_a_readable_error(wired):
    wired([], returncode=1, stderr="Invalid API key")
    with pytest.raises(EngineError) as exc:
        list(ClaudeEngine().answer_text("why?"))
    assert "Invalid API key" in str(exc.value)


def test_a_nonzero_exit_without_stderr_still_names_the_cli(wired):
    wired([], returncode=2, stderr="")
    with pytest.raises(EngineError) as exc:
        list(AgyEngine().answer_text("why?"))
    assert "agy" in str(exc.value)


def test_a_clean_exit_after_text_raises_nothing(wired):
    wired(claude_lines("done"), returncode=0)
    assert "".join(ClaudeEngine().answer_text("why?")) == "done"


# ── registry ────────────────────────────────────────────────────────────────

def test_get_engine_returns_the_right_class():
    assert isinstance(get_engine("claude"), ClaudeEngine)
    assert isinstance(get_engine("agy"), AgyEngine)


def test_get_engine_rejects_an_unknown_name():
    with pytest.raises(KeyError):
        get_engine("gpt")


def test_installed_lists_only_what_is_on_the_machine(monkeypatch):
    monkeypatch.setattr(
        engines.base.shutil, "which",
        lambda name: "C:/fake/agy.exe" if name == "agy" else None,
    )
    names = [m.name for m in installed()]
    assert names == ["agy"]


def test_installed_rows_render_in_the_model_picker(monkeypatch):
    """The picker draws provider/name/capabilities, so CLIs must fit that shape."""
    monkeypatch.setattr(engines.base.shutil, "which", lambda name: "C:/fake/cli.exe")
    for row in installed():
        assert row.provider and row.name
        assert "vision" in row.capabilities
        assert "audio" not in row.capabilities  # neither CLI transcribes


# ── Windows: the npm .CMD shim cannot carry a multi-line argument ───────────

def test_a_cmd_shim_is_followed_to_the_real_executable(monkeypatch, tmp_path):
    """cmd.exe cuts the command at the first newline, and PROMPT has 13."""
    real = tmp_path / "node_modules" / "pkg" / "bin" / "claude.exe"
    real.parent.mkdir(parents=True)
    real.write_bytes(b"MZ")
    shim = tmp_path / "claude.cmd"
    shim.write_text(
        '@ECHO off\nSET dp0=%~dp0\n'
        + r'"%dp0%\node_modules\pkg\bin\claude.exe"   %*' + '\n',
        encoding="utf-8",
    )
    record = {}
    monkeypatch.setattr(engines.base.shutil, "which", lambda name: str(shim))
    monkeypatch.setattr(
        engines.base.subprocess, "Popen", fake_popen(claude_lines("hi"), record=record)
    )
    list(ClaudeEngine().answer_text("why?"))
    assert record["argv"][0] == str(real)


def test_a_plain_exe_is_left_alone(wired):
    record = wired(claude_lines("hi"), exe="C:/tools/agy.exe")
    list(AgyEngine().answer_text("why?"))
    assert record["argv"][0] == "C:/tools/agy.exe"


def test_a_shim_pointing_nowhere_falls_back_to_itself(monkeypatch, tmp_path):
    shim = tmp_path / "claude.cmd"
    shim.write_text(r'"%dp0%\gone\claude.exe" %*' + '\n', encoding="utf-8")
    record = {}
    monkeypatch.setattr(engines.base.shutil, "which", lambda name: str(shim))
    monkeypatch.setattr(
        engines.base.subprocess, "Popen", fake_popen(claude_lines("hi"), record=record)
    )
    list(ClaudeEngine().answer_text("why?"))
    assert record["argv"][0] == str(shim)


def test_the_prompt_really_does_contain_newlines():
    """Guards the reason the shim matters: a one-line prompt would hide the bug."""
    from phonexi.engines.base import system_prompt
    assert "\n" in system_prompt()


# ── claude only reads inside its working directory ─────────────────────────

def test_claude_is_given_the_screenshot_directory(wired, tmp_path):
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_image(shot))
    argv = record["argv"]
    assert argv[argv.index("--add-dir") + 1] == str(tmp_path)


def test_text_mode_does_not_widen_the_directory(wired):
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?"))
    assert "--add-dir" not in record["argv"]


def test_image_mode_tells_the_agent_not_to_narrate(wired, tmp_path):
    """An agent that says "I'll read the screenshot first" wastes the opening line."""
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_image(shot))
    sent = record["argv"][record["argv"].index("-p") + 1]
    assert "do not narrate" in sent


def test_agy_asks_for_the_configured_effort(wired):
    """Without it agy takes whatever tier its own config happens to hold."""
    from phonexi.config import AGY_EFFORT
    record = wired(agy_lines("hi"))
    list(AgyEngine().answer_text("why?"))
    argv = record["argv"]
    assert argv[argv.index("--effort") + 1] == AGY_EFFORT


def test_agy_defaults_to_high_effort():
    from phonexi.config import AGY_EFFORT
    assert AGY_EFFORT == "high"
