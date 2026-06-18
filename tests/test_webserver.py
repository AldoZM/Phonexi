import socket
from unittest.mock import patch

from phonexi.webserver import lan_ip, find_free_port, format_sse


def test_format_sse_shape():
    frame = format_sse("status", {"text": "hi"})
    assert frame.startswith("event: status\n")
    assert 'data: {"text": "hi"}' in frame
    assert frame.endswith("\n\n")


def test_lan_ip_fallback_on_error():
    with patch("phonexi.webserver.socket.socket") as mock_sock:
        mock_sock.return_value.connect.side_effect = OSError("no net")
        assert lan_ip() == "localhost"


def test_lan_ip_returns_socket_name():
    with patch("phonexi.webserver.socket.socket") as mock_sock:
        inst = mock_sock.return_value
        inst.getsockname.return_value = ("192.168.1.42", 12345)
        assert lan_ip() == "192.168.1.42"


def test_find_free_port_skips_taken():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("", 0))
        taken_port = taken.getsockname()[1]
        taken.listen()
        port = find_free_port(start=taken_port, end=taken_port + 5)
        assert taken_port < port <= taken_port + 5
