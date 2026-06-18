import io
import sys
from unittest.mock import patch

import main


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
