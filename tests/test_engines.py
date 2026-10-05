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
    from phonexi.engines import agy
    monkeypatch.setattr(
        engines.base.shutil, "which",
        lambda name: "C:/fake/agy.exe" if name == "agy" else None,
    )
    monkeypatch.setattr(agy, "list_models", lambda exe: [])
    assert [m.provider for m in installed()] == ["agy"]


def test_installed_rows_render_in_the_model_picker(monkeypatch):
    """The picker draws provider/name/capabilities, so CLIs must fit that shape."""
    from phonexi.engines import agy
    monkeypatch.setattr(engines.base.shutil, "which", lambda name: "C:/fake/cli.exe")
    monkeypatch.setattr(agy, "list_models", lambda exe: [])
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
    assert "\n" in system_prompt(voice=True)
    assert "\n" in system_prompt(voice=False)


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


def test_agy_defaults_to_low_effort(monkeypatch):
    # low spent 0 thinking tokens on 2026-09-22 and was 0.24 s faster to the
    # first word than medium on 2026-09-20. Read with no .env override.
    import importlib
    from phonexi import config
    monkeypatch.delenv("AGY_EFFORT", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    try:
        assert importlib.reload(config).AGY_EFFORT == "low"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


# ── agy models: one row per family, effort on Left/Right ────────────────────

AGY_MODELS_OUTPUT = """Fetching available models...
gemini-3.8-flash-high\tGemini 3.8 Flash (High)
gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)
gemini-3.8-flash-low\tGemini 3.8 Flash (Low)
gemini-3.1-pro-high\tGemini 3.1 Pro (High)
gemini-3.1-pro-low\tGemini 3.1 Pro (Low)
claude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)
gpt-oss-120b-medium\tGPT-OSS 120B (Medium)
"""


def test_agy_models_are_grouped_by_family():
    from phonexi.engines.agy import parse_models
    rows = parse_models(AGY_MODELS_OUTPUT)
    assert [r.name for r in rows] == [
        "Gemini 3.8 Flash", "Gemini 3.1 Pro", "Claude Sonnet 4.6 (Thinking)", "GPT-OSS 120B",
    ]
    assert all(r.provider == "agy" for r in rows)


def test_agy_levels_come_in_speed_order():
    from phonexi.engines.agy import parse_models
    flash = parse_models(AGY_MODELS_OUTPUT)[0]
    assert flash.levels == ("low", "medium", "high")


def test_agy_level_starts_on_agy_effort():
    from phonexi.engines.agy import parse_models
    flash = parse_models(AGY_MODELS_OUTPUT, default="medium")[0]
    assert flash.level == "medium"
    assert flash.model_id == "gemini-3.8-flash-medium"


def test_agy_level_falls_back_to_low_when_the_default_is_missing():
    # high took 17x longer to the first word, so a missing medium means low.
    from phonexi.engines.agy import parse_models
    pro = parse_models(AGY_MODELS_OUTPUT, default="medium")[1]
    assert pro.levels == ("low", "high")
    assert pro.level == "low"


def test_agy_model_without_levels_keeps_its_own_id():
    from phonexi.engines.agy import parse_models
    sonnet = parse_models(AGY_MODELS_OUTPUT)[2]
    assert sonnet.levels == ()
    assert sonnet.model_id == "claude-sonnet-4-6"


def test_choosing_another_level_changes_the_model_id():
    import dataclasses
    from phonexi.engines.agy import parse_models
    flash = parse_models(AGY_MODELS_OUTPUT)[0]
    assert dataclasses.replace(flash, level="high").model_id == "gemini-3.8-flash-high"


def test_agy_models_output_without_models_gives_nothing():
    from phonexi.engines.agy import parse_models
    assert parse_models("Fetching available models...\n") == []


def test_list_models_runs_agy_models_with_a_timeout(monkeypatch):
    from phonexi.engines import agy
    seen = {}

    def run(argv, **kwargs):
        seen["argv"], seen["timeout"] = argv, kwargs.get("timeout")
        return subprocess.CompletedProcess(argv, 0, stdout=AGY_MODELS_OUTPUT, stderr="")

    monkeypatch.setattr(agy.subprocess, "run", run)
    rows = agy.list_models("C:/fake/agy.exe")
    assert seen["argv"] == ["C:/fake/agy.exe", "models"]
    assert seen["timeout"] and seen["timeout"] <= 10
    assert len(rows) == 4


@pytest.mark.parametrize("failure", ["timeout", "exit", "oserror"])
def test_list_models_failure_gives_nothing(monkeypatch, failure):
    from phonexi.engines import agy

    def run(argv, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, 10)
        if failure == "oserror":
            raise OSError("boom")
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="auth")

    monkeypatch.setattr(agy.subprocess, "run", run)
    assert agy.list_models("C:/fake/agy.exe") == []


def _only(monkeypatch, *present):
    monkeypatch.setattr(
        engines.base.shutil, "which",
        lambda name: f"C:/fake/{name}.exe" if name in present else None,
    )


def test_installed_lists_agy_models_then_claude(monkeypatch):
    from phonexi.engines import agy
    _only(monkeypatch, "agy", "claude")
    monkeypatch.setattr(agy, "list_models", lambda exe: agy.parse_models(AGY_MODELS_OUTPUT))
    rows = installed()
    assert [r.provider for r in rows] == ["agy"] * 4 + ["claude"]
    assert rows[-1].levels == ("low", "medium", "high")
    assert rows[-1].level == "medium"


def test_installed_falls_back_to_one_agy_row_without_a_model_list(monkeypatch):
    from phonexi.engines import agy
    _only(monkeypatch, "agy")
    monkeypatch.setattr(agy, "list_models", lambda exe: [])
    rows = installed()
    assert len(rows) == 1
    assert rows[0].provider == "agy"
    assert rows[0].model_id is None
    assert rows[0].levels == ("low", "medium", "high")


def test_agy_with_a_model_passes_it_and_no_effort(wired):
    record = wired(agy_lines("ok"))
    list(AgyEngine(model="gemini-3.8-flash-low").answer_text("why?"))
    argv = record["argv"]
    assert argv[argv.index("--model") + 1] == "gemini-3.8-flash-low"
    assert "--effort" not in argv


def test_agy_without_a_model_passes_the_effort(wired):
    record = wired(agy_lines("ok"))
    list(AgyEngine(effort="low").answer_text("why?"))
    argv = record["argv"]
    assert "--model" not in argv
    assert argv[argv.index("--effort") + 1] == "low"


def test_claude_passes_the_chosen_effort(wired):
    record = wired(claude_lines("ok"))
    list(ClaudeEngine(effort="low").answer_text("why?"))
    argv = record["argv"]
    assert argv[argv.index("--effort") + 1] == "low"


def test_claude_without_an_effort_sends_none(wired):
    record = wired(claude_lines("ok"))
    list(ClaudeEngine().answer_text("why?"))
    assert "--effort" not in record["argv"]


def test_engine_for_maps_a_choice_to_its_engine():
    import dataclasses
    from phonexi.engines import engine_for
    from phonexi.engines.agy import parse_models
    from phonexi.engines.base import CliChoice

    flash = dataclasses.replace(parse_models(AGY_MODELS_OUTPUT)[0], level="low")
    agy_engine = engine_for(flash)
    assert isinstance(agy_engine, AgyEngine)
    assert agy_engine.model == "gemini-3.8-flash-low"

    claude = engine_for(CliChoice("claude", "Claude Code", ("low", "medium", "high"), "high"))
    assert isinstance(claude, ClaudeEngine)
    assert claude.effort == "high"


# ── each hotkey carries its own prompt ──────────────────────────────────────

def test_claude_answers_voice_with_the_voice_prompt(wired):
    from phonexi.config import PROMPT_VOICE
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_text("why?"))
    argv = record["argv"]
    assert argv[argv.index("--system-prompt") + 1] == PROMPT_VOICE


def test_claude_answers_a_capture_with_the_capture_prompt(wired, tmp_path):
    from phonexi.config import PROMPT_CAPTURE
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    record = wired(claude_lines("hi"))
    list(ClaudeEngine().answer_image(shot))
    argv = record["argv"]
    assert argv[argv.index("--system-prompt") + 1] == PROMPT_CAPTURE


def test_agy_prepends_the_prompt_of_each_mode(wired, tmp_path):
    from phonexi.config import PROMPT_CAPTURE, PROMPT_VOICE
    record = wired(agy_lines("hi"))
    list(AgyEngine().answer_text("why?"))
    assert record["argv"][record["argv"].index("-p") + 1].startswith(PROMPT_VOICE)
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    record = wired(agy_lines("hi"))
    list(AgyEngine().answer_image(shot))
    assert record["argv"][record["argv"].index("-p") + 1].startswith(PROMPT_CAPTURE)
