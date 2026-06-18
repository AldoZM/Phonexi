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
