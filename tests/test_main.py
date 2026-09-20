import io
import sys
from unittest.mock import MagicMock, patch

import pytest

import main
from phonexi.briefing import BriefingError


@pytest.fixture(autouse=True)
def never_prune_for_real():
    """Keep the suite off the real screenshots folder.

    Startup pruning deletes files, and most tests here call main() for other
    reasons — without this every test run would wipe the developer's captures.
    Tests that assert on pruning patch it again themselves.
    """
    with patch("main.prune"):
        yield


def test_parse_args_short_flag():
    with patch.object(sys, "argv", ["main.py", "-P"]):
        assert main._parse_args().primary is True


def test_parse_args_long_flag():
    with patch.object(sys, "argv", ["main.py", "--primary"]):
        assert main._parse_args().primary is True


def test_parse_args_default_false():
    with patch.object(sys, "argv", ["main.py"]):
        assert main._parse_args().primary is False


def test_parse_args_web_short_flag():
    with patch.object(sys, "argv", ["main.py", "-w"]):
        assert main._parse_args().web is True


def test_parse_args_web_long_flag():
    with patch.object(sys, "argv", ["main.py", "--web"]):
        assert main._parse_args().web is True


def test_parse_args_web_default_false():
    with patch.object(sys, "argv", ["main.py"]):
        assert main._parse_args().web is False


def test_main_web_mode_starts_server_and_listener():
    argv = ["main.py", "--web"]
    with patch.object(sys, "argv", argv), \
         patch("main._print_qr"), \
         patch("phonexi.webserver.WebServer") as mock_server_cls, \
         patch("phonexi.webserver.lan_ip", return_value="192.168.1.42"), \
         patch("main.HotkeyListener") as mock_listener_cls, \
         patch("main.tk.Tk") as mock_tk:
        mock_server_cls.return_value.port = 8000
        main.main()
        mock_server_cls.assert_called_once()
        mock_server_cls.return_value.start.assert_called_once()
        mock_listener_cls.return_value.start.assert_called_once()
        mock_tk.assert_not_called()  # web mode never touches tkinter


def test_print_qr_survives_cp1252_console(monkeypatch):
    # Simulate a Windows cp1252 console that cannot encode block glyphs.
    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    # Must not raise UnicodeEncodeError.
    main._print_qr("http://192.168.1.42:8000")


def test_parse_args_context_short_flag():
    with patch.object(sys, "argv", ["main.py", "-c", "brief.md"]):
        assert main._parse_args().context == "brief.md"


def test_parse_args_context_long_flag():
    with patch.object(sys, "argv", ["main.py", "--context", "brief.md"]):
        assert main._parse_args().context == "brief.md"


def test_parse_args_context_defaults_to_none():
    with patch.object(sys, "argv", ["main.py"]):
        assert main._parse_args().context is None


def test_main_without_context_flag_never_reads_a_file():
    with patch.object(sys, "argv", ["main.py"]), \
         patch("main.load_briefing") as mock_load, \
         patch("main.HotkeyListener"), \
         patch("main.tk.Tk"):
        main.main()
    mock_load.assert_not_called()


def test_main_loads_briefing_before_starting_the_listener():
    calls = []
    with patch.object(sys, "argv", ["main.py", "-c", "brief.md"]), \
         patch("main.load_briefing", side_effect=lambda p: calls.append("load") or "CTX"), \
         patch("main.HotkeyListener", side_effect=lambda **kw: calls.append("listener") or MagicMock()), \
         patch("main.tk.Tk"):
        main.main()
    assert calls == ["load", "listener"]


def test_main_passes_briefing_to_the_listener():
    with patch.object(sys, "argv", ["main.py", "-c", "brief.md"]), \
         patch("main.load_briefing", return_value="Vacante Kafka."), \
         patch("main.HotkeyListener") as mock_listener_cls, \
         patch("main.tk.Tk"):
        main.main()
    assert mock_listener_cls.call_args.kwargs["briefing"] == "Vacante Kafka."


def test_web_mode_passes_briefing_to_the_listener():
    with patch.object(sys, "argv", ["main.py", "-w", "-c", "brief.md"]), \
         patch("main._print_qr"), \
         patch("main.load_briefing", return_value="Vacante Kafka."), \
         patch("phonexi.webserver.WebServer") as mock_server_cls, \
         patch("phonexi.webserver.lan_ip", return_value="192.168.1.42"), \
         patch("main.HotkeyListener") as mock_listener_cls:
        mock_server_cls.return_value.port = 8000
        main.main()
    assert mock_listener_cls.call_args.kwargs["briefing"] == "Vacante Kafka."


def test_main_exits_when_briefing_is_invalid():
    with patch.object(sys, "argv", ["main.py", "-c", "no_existe.md"]), \
         patch("main.load_briefing", side_effect=BriefingError("no_existe.md: file not found")), \
         patch("main.HotkeyListener") as mock_listener_cls, \
         patch("main.tk.Tk"):
        with pytest.raises(SystemExit) as exc:
            main.main()
    assert exc.value.code == 1
    mock_listener_cls.assert_not_called()


def test_main_prints_the_reason_when_briefing_is_invalid(capsys):
    with patch.object(sys, "argv", ["main.py", "-c", "no_existe.md"]), \
         patch("main.load_briefing", side_effect=BriefingError("no_existe.md: file not found")), \
         patch("main.tk.Tk"):
        with pytest.raises(SystemExit):
            main.main()
    assert "no_existe.md: file not found" in capsys.readouterr().out


def test_parse_args_region_defaults_to_none():
    with patch.object(sys, "argv", ["main.py"]):
        assert main._parse_args().region is None


def test_parse_args_bare_region_flag_uses_the_default_size():
    from phonexi.screenshot import DEFAULT_REGION

    with patch.object(sys, "argv", ["main.py", "-r"]):
        assert main._parse_args().region == DEFAULT_REGION


def test_parse_args_region_accepts_an_explicit_size():
    with patch.object(sys, "argv", ["main.py", "--region", "960x540"]):
        assert main._parse_args().region == (960, 540)


def test_parse_args_region_rejects_junk():
    with patch.object(sys, "argv", ["main.py", "-r", "huge"]):
        with pytest.raises(SystemExit):
            main._parse_args()


def test_main_forwards_the_region_to_the_listener():
    with patch.object(sys, "argv", ["main.py", "-r", "960x540"]), \
         patch("main.tk.Tk"), \
         patch("main.threading.Thread"), \
         patch("main.prune"), \
         patch("main.HotkeyListener") as mock_listener_cls:
        main.main()

    assert mock_listener_cls.call_args.kwargs["region"] == (960, 540)


def test_main_prunes_old_captures_at_startup():
    with patch.object(sys, "argv", ["main.py"]), \
         patch("main.tk.Tk"), \
         patch("main.threading.Thread"), \
         patch("main.HotkeyListener"), \
         patch("main.prune") as mock_prune:
        main.main()

    mock_prune.assert_called_once()


# ── -model / provider selection ──────────────────────────────────────────────

@pytest.mark.parametrize("flag", ["-model", "--model", "-m"])
def test_parse_args_model_flag_spellings(flag):
    with patch.object(sys, "argv", ["main.py", flag]):
        assert main._parse_args().model is True


def test_parse_args_model_default_false():
    with patch.object(sys, "argv", ["main.py"]):
        assert main._parse_args().model is False


@pytest.mark.parametrize("flag", ["-h", "-help", "--help"])
def test_help_flag_spellings_print_help(flag, capsys):
    with patch.object(sys, "argv", ["main.py", flag]):
        with pytest.raises(SystemExit) as info:
            main._parse_args()
    assert info.value.code == 0
    out = capsys.readouterr().out
    assert "-model" in out
    assert "GEMINI_API_KEY" in out
    assert "Examples" in out


def test_main_without_model_flag_activates_the_top_key():
    from phonexi.providers import GEMINI
    with patch.object(sys, "argv", ["main.py"]), \
         patch("main.key_order", return_value=[GEMINI]), \
         patch("main.choose") as mock_choose, \
         patch("main.activate") as mock_activate, \
         patch("main._run_popup"):
        main.main()
    mock_choose.assert_not_called()
    assert mock_activate.call_args.args[0].provider == GEMINI


def test_main_model_flag_activates_the_chosen_model():
    from phonexi.providers import find
    picked = find("gemini-3.8-flash")
    with patch.object(sys, "argv", ["main.py", "-model"]), \
         patch("main.key_order", return_value=["gemini", "groq"]), \
         patch("main.choose", return_value=picked), \
         patch("main.activate") as mock_activate, \
         patch("main._run_popup") as mock_run:
        main.main()
    sel = mock_activate.call_args.args[0]
    assert sel.text_model == sel.vision_model == "gemini-3.8-flash"
    mock_run.assert_called_once()


def test_main_model_flag_cancelled_exits_without_starting():
    with patch.object(sys, "argv", ["main.py", "-model"]), \
         patch("main.key_order", return_value=["gemini"]), \
         patch("main.choose", return_value=None), \
         patch("main._run_popup") as mock_run:
        with pytest.raises(SystemExit) as info:
            main.main()
    assert info.value.code == 0
    mock_run.assert_not_called()


def test_main_model_flag_without_terminal_exits_with_error(capsys):
    from phonexi.picker import PickerUnavailableError
    with patch.object(sys, "argv", ["main.py", "-model"]), \
         patch("main.key_order", return_value=["gemini"]), \
         patch("main.choose", side_effect=PickerUnavailableError("no terminal")), \
         patch("main._run_popup") as mock_run:
        with pytest.raises(SystemExit) as info:
            main.main()
    assert info.value.code == 1
    mock_run.assert_not_called()
    assert "no terminal" in capsys.readouterr().out


def test_main_model_flag_starts_on_the_current_default():
    with patch.object(sys, "argv", ["main.py", "-model"]), \
         patch("main.key_order", return_value=["groq", "gemini"]), \
         patch("main.choose", return_value=None) as mock_choose, \
         patch("main._run_popup"):
        with pytest.raises(SystemExit):
            main.main()
    models = mock_choose.call_args.args[0]
    start = mock_choose.call_args.kwargs["start"]
    assert models[start].provider == "groq"

