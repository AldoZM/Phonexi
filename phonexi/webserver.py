import json
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator


def lan_ip() -> str:
    """Best-effort LAN IP. Returns 'localhost' if it can't be determined."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packet sent; just picks the route
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def find_free_port(start: int = 8000, end: int = 8010) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in {start}-{end}")


def format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


class Broadcaster:
    """Fan-out de eventos a clientes SSE. Guarda el último evento para
    entregarlo a clientes que se conectan tarde."""

    def __init__(self) -> None:
        self._clients: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._last: tuple[str, dict] | None = None

    def register(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._clients.append(q)
            if self._last is not None:
                q.put(self._last)
        return q

    def unregister(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def publish(self, event: str, payload: dict) -> None:
        with self._lock:
            self._last = (event, payload)
            for q in self._clients:
                q.put((event, payload))


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phonexi</title>
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/base16/dracula.min.css">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
<style>
  body { background:#0d0d0d; color:#e0e0e0; margin:0;
         font-family:'Cascadia Code',Consolas,monospace; }
  #status { color:#6272a4; padding:10px 16px; font-size:14px; }
  #status.err { color:#ff5555; }
  #response { padding:0 16px 24px; line-height:1.5; }
  #response strong { background:#f1fa8c; color:#282a36; padding:0 3px; }
  #response h1,#response h2,#response h3 { color:#8be9fd; }
  #response code { color:#50fa7b; background:#1c1c1c; padding:0 3px; }
  #response pre { background:#141414; padding:12px; border-radius:6px;
                  overflow-x:auto; }
  #response pre code { background:none; color:inherit; }
</style>
</head>
<body>
<div id="status">Waiting for Phonexi...</div>
<div id="response"></div>
<script>
  const statusEl = document.getElementById('status');
  const respEl = document.getElementById('response');
  const es = new EventSource('/events');
  es.addEventListener('status', e => {
    statusEl.className = '';
    statusEl.textContent = JSON.parse(e.data).text;
  });
  es.addEventListener('error', e => {
    if (!e.data) return;
    statusEl.className = 'err';
    statusEl.textContent = JSON.parse(e.data).text;
  });
  es.addEventListener('response', e => {
    respEl.innerHTML = marked.parse(JSON.parse(e.data).markdown);
    respEl.querySelectorAll('pre code').forEach(b => hljs.highlightElement(b));
  });
</script>
</body>
</html>
"""


def _make_handler(broadcaster: Broadcaster):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # silence stdout noise
            pass

        def do_GET(self) -> None:
            if self.path == "/events":
                self._serve_events()
            else:
                self._serve_index()

        def _serve_index(self) -> None:
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = broadcaster.register()
            try:
                while True:
                    event, payload = q.get()
                    self.wfile.write(format_sse(event, payload).encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                broadcaster.unregister(q)

    return _Handler


class WebServer:
    def __init__(self, host: str = "0.0.0.0", port: int | None = None) -> None:
        self.broadcaster = Broadcaster()
        self.host = host
        self.port = port if port is not None else find_free_port()
        self._httpd = ThreadingHTTPServer((host, self.port), _make_handler(self.broadcaster))
        self._started = False

    def start(self) -> None:
        self._started = True
        ready = threading.Event()

        def _serve() -> None:
            ready.set()
            self._httpd.serve_forever()

        threading.Thread(target=_serve, daemon=True).start()
        ready.wait(timeout=5)

    def publish(self, event: str, payload: dict) -> None:
        self.broadcaster.publish(event, payload)

    def stop(self) -> None:
        if self._started:
            self._httpd.shutdown()
        self._httpd.server_close()


class WebView:
    """Sink con la misma interfaz pública que ui.ResultWindow, pero publica
    al WebServer en vez de dibujar en tkinter."""

    def __init__(self, server: "WebServer") -> None:
        self._server = server

    def show_status(self, msg: str) -> None:
        self._server.publish("status", {"text": msg})

    def show_error(self, msg: str) -> None:
        self._server.publish("error", {"text": msg})

    def show_and_collect(self, iterator: Iterator[str]) -> str:
        full = "".join(iterator)
        self._server.publish("response", {"markdown": full})
        return full

    def show(self, iterator: Iterator[str]) -> None:
        self.show_and_collect(iterator)

    def close(self) -> None:
        pass
