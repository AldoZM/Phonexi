import socket
import urllib.request
from unittest.mock import MagicMock, patch

from phonexi.webserver import lan_ip, find_free_port, format_sse, Broadcaster, WebView, WebServer, INDEX_HTML


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


def test_broadcaster_publish_reaches_all_clients():
    b = Broadcaster()
    q1 = b.register()
    q2 = b.register()
    b.publish("status", {"text": "x"})
    assert q1.get_nowait() == ("status", {"text": "x"})
    assert q2.get_nowait() == ("status", {"text": "x"})


def test_broadcaster_new_client_gets_last_event():
    b = Broadcaster()
    b.publish("response", {"markdown": "**hi**"})
    q = b.register()
    assert q.get_nowait() == ("response", {"markdown": "**hi**"})


def test_broadcaster_unregister_stops_delivery():
    b = Broadcaster()
    q = b.register()
    b.unregister(q)
    b.publish("status", {"text": "y"})
    assert q.empty()


def test_webview_show_status_publishes():
    server = MagicMock()
    WebView(server).show_status("Listening...")
    server.publish.assert_called_once_with("status", {"text": "Listening..."})


def test_webview_show_error_publishes():
    server = MagicMock()
    WebView(server).show_error("boom")
    server.publish.assert_called_once_with("error", {"text": "boom"})


def test_webview_show_and_collect_joins_and_returns():
    server = MagicMock()
    result = WebView(server).show_and_collect(iter(["hel", "lo"]))
    assert result == "hello"
    server.publish.assert_called_once_with("response", {"markdown": "hello"})


def test_webview_close_is_noop():
    WebView(MagicMock()).close()  # must not raise


def test_index_html_references_eventsource_and_libs():
    assert "EventSource('/events')" in INDEX_HTML
    assert "marked" in INDEX_HTML
    assert "highlight" in INDEX_HTML


def test_webserver_picks_port_and_serves_index():
    server = WebServer(host="127.0.0.1")
    server.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.port}/", timeout=5
        ) as resp:
            body = resp.read().decode()
            assert resp.status == 200
            assert "EventSource('/events')" in body
    finally:
        server.stop()


def test_webserver_publish_delegates_to_broadcaster():
    server = WebServer(host="127.0.0.1")
    q = server.broadcaster.register()
    server.publish("status", {"text": "z"})
    assert q.get_nowait() == ("status", {"text": "z"})
    server.stop()
