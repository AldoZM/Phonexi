# Salida web (`-w`/`--web`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar un flag `-w`/`--web` que, en vez del popup tkinter, sirve las respuestas en un servidor local (SSE) leíble desde el celular vía QR, sin exponer nada en pantalla compartida.

**Architecture:** Nuevo módulo `phonexi/webserver.py` con un `ThreadingHTTPServer` (stdlib) que expone `/` (página HTML) y `/events` (SSE). Un `Broadcaster` thread-safe distribuye eventos a los clientes y guarda el último estado. `WebView` implementa la misma interfaz que `ResultWindow`. El `HotkeyListener` se parametriza con un `view_factory` y un `_schedule` para funcionar con o sin tkinter.

**Tech Stack:** Python 3.10+, `http.server`/`socketserver`/`socket`/`queue`/`threading`/`json` (stdlib), `qrcode` (QR ASCII en terminal), marked.js + highlight.js (CDN, cliente).

## Global Constraints

- Python 3.10+ (sintaxis `X | None` permitida; el repo ya la usa).
- Sin dependencias nuevas salvo `qrcode>=7.4` (modo ASCII, sin Pillow).
- Modo web NO crea ninguna ventana tkinter; `--primary` se ignora en modo web.
- Los hotkeys no cambian: `RShift+P`, `RAlt+P`, `Esc`.
- No agregar atribución de IA a los mensajes de commit.
- Plataforma destino: Windows 10/11.
- Tests con pytest; los tests tkinter existentes deben seguir pasando.

---

### Task 1: Flag `-w`/`--web` en main.py

**Files:**
- Modify: `main.py:10-17` (`_parse_args`)
- Test: `tests/test_main.py`

**Interfaces:**
- Produces: `_parse_args()` devuelve `Namespace` con atributo booleano `web` (default `False`), además del `primary` existente.

- [ ] **Step 1: Escribir tests que fallan**

Agregar a `tests/test_main.py`:

```python
def test_parse_args_web_short_flag():
    with patch.object(sys, "argv", ["main.py", "-w"]):
        assert main._parse_args().web is True


def test_parse_args_web_long_flag():
    with patch.object(sys, "argv", ["main.py", "--web"]):
        assert main._parse_args().web is True


def test_parse_args_web_default_false():
    with patch.object(sys, "argv", ["main.py"]):
        assert main._parse_args().web is False
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'web'`

- [ ] **Step 3: Implementar el flag**

En `main.py`, dentro de `_parse_args`, antes de `return parser.parse_args()`:

```python
    parser.add_argument(
        "-w", "--web",
        action="store_true",
        help="Serve responses on a local web server (read on your phone via QR) "
             "instead of the on-screen popup.",
    )
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (los 6 tests).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: parse -w/--web flag"
```

---

### Task 2: Utilidades de red — `lan_ip`, `find_free_port`, `format_sse`

**Files:**
- Create: `phonexi/webserver.py`
- Test: `tests/test_webserver.py`

**Interfaces:**
- Produces:
  - `lan_ip() -> str` — IP LAN, o `"localhost"` si falla el socket.
  - `find_free_port(start: int = 8000, end: int = 8010) -> int` — primer puerto libre; `RuntimeError` si ninguno.
  - `format_sse(event: str, payload: dict) -> str` — frame SSE `event: <e>\ndata: <json>\n\n`.

- [ ] **Step 1: Escribir tests que fallan**

Crear `tests/test_webserver.py`:

```python
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
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phonexi.webserver'`

- [ ] **Step 3: Implementar utilidades**

Crear `phonexi/webserver.py`:

```python
import json
import socket


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
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add phonexi/webserver.py tests/test_webserver.py
git commit -m "feat: web server net utils (lan_ip, find_free_port, format_sse)"
```

---

### Task 3: `Broadcaster` thread-safe con último estado

**Files:**
- Modify: `phonexi/webserver.py`
- Test: `tests/test_webserver.py`

**Interfaces:**
- Produces: clase `Broadcaster` con:
  - `register() -> queue.Queue` — registra cliente; si hay último evento, lo encola de inmediato.
  - `unregister(q: queue.Queue) -> None`
  - `publish(event: str, payload: dict) -> None` — guarda `(event, payload)` como último y lo encola a todos los clientes.
  - Cada item en la cola es la tupla `(event: str, payload: dict)`.

- [ ] **Step 1: Escribir tests que fallan**

Agregar a `tests/test_webserver.py`:

```python
from phonexi.webserver import Broadcaster


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
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: FAIL — `ImportError: cannot import name 'Broadcaster'`

- [ ] **Step 3: Implementar `Broadcaster`**

En `phonexi/webserver.py`, agregar imports `queue` y `threading` arriba, y la clase:

```python
import queue
import threading


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
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add phonexi/webserver.py tests/test_webserver.py
git commit -m "feat: thread-safe Broadcaster with last-event replay"
```

---

### Task 4: `WebView` (interfaz espejo de `ResultWindow`)

**Files:**
- Modify: `phonexi/webserver.py`
- Test: `tests/test_webserver.py`

**Interfaces:**
- Consumes: un objeto con método `publish(event: str, payload: dict)` (el `WebServer`, o un mock).
- Produces: clase `WebView` con:
  - `show_status(msg: str) -> None` → `publish("status", {"text": msg})`
  - `show_and_collect(iterator) -> str` → consume el iterator, junta el texto, `publish("response", {"markdown": full})`, devuelve `full`.
  - `show(iterator) -> None` → llama `show_and_collect` y descarta el retorno.
  - `show_error(msg: str) -> None` → `publish("error", {"text": msg})`
  - `close() -> None` → no-op.

- [ ] **Step 1: Escribir tests que fallan**

Agregar a `tests/test_webserver.py`:

```python
from unittest.mock import MagicMock

from phonexi.webserver import WebView


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
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: FAIL — `ImportError: cannot import name 'WebView'`

- [ ] **Step 3: Implementar `WebView`**

En `phonexi/webserver.py`, agregar:

```python
from typing import Iterator


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
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add phonexi/webserver.py tests/test_webserver.py
git commit -m "feat: WebView sink mirroring ResultWindow interface"
```

---

### Task 5: `WebServer` (HTTP + SSE + página HTML)

**Files:**
- Modify: `phonexi/webserver.py`
- Test: `tests/test_webserver.py`

**Interfaces:**
- Consumes: `Broadcaster`, `find_free_port`, `format_sse`.
- Produces: clase `WebServer`:
  - `__init__(host: str = "0.0.0.0", port: int | None = None)` — si `port` es `None`, usa `find_free_port()`; expone `self.port`, `self.host`, `self.broadcaster`.
  - `start() -> None` — corre `serve_forever` en thread daemon.
  - `publish(event: str, payload: dict) -> None` — delega en `self.broadcaster`.
  - `stop() -> None` — `shutdown()` del httpd.
  - Constante de módulo `INDEX_HTML: str`.

- [ ] **Step 1: Escribir tests que fallan**

Agregar a `tests/test_webserver.py`:

```python
import urllib.request

from phonexi.webserver import WebServer, INDEX_HTML


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
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: FAIL — `ImportError: cannot import name 'WebServer'`

- [ ] **Step 3: Implementar `WebServer`, handler e `INDEX_HTML`**

En `phonexi/webserver.py`, agregar imports y el resto:

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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

    def start(self) -> None:
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def publish(self, event: str, payload: dict) -> None:
        self.broadcaster.publish(event, payload)

    def stop(self) -> None:
        self._httpd.shutdown()
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_webserver.py -v`
Expected: PASS (14 tests).

- [ ] **Step 5: Commit**

```bash
git add phonexi/webserver.py tests/test_webserver.py
git commit -m "feat: WebServer with SSE endpoint and dark HTML page"
```

---

### Task 6: Refactor del listener — `view_factory`, `_schedule`, `close()`

**Files:**
- Modify: `phonexi/listener.py`
- Modify: `phonexi/ui.py` (agregar `close()`)
- Test: `tests/test_listener.py`, `tests/test_ui.py`

**Interfaces:**
- Consumes: `WebView` / `ResultWindow` como vistas intercambiables.
- Produces:
  - `HotkeyListener.__init__(self, tk_root=None, use_primary=False, view_factory=None)`.
  - `HotkeyListener._schedule(self, fn, *args)`.
  - `ResultWindow.close(self) -> None`.

- [ ] **Step 1: Agregar `close()` a `ResultWindow` (test primero)**

Agregar a `tests/test_ui.py`:

```python
def test_result_window_close_destroys(root):
    win = ResultWindow(root)
    win.close()
    assert not win._win.winfo_exists()
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_ui.py::test_result_window_close_destroys -v`
Expected: FAIL — `AttributeError: 'ResultWindow' object has no attribute 'close'`

- [ ] **Step 3: Implementar `close()`**

En `phonexi/ui.py`, dentro de `ResultWindow` (junto a la sección public API):

```python
    def close(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_ui.py -v`
Expected: PASS (todos, incluido el nuevo).

- [ ] **Step 5: Test del listener sin tkinter (web)**

Agregar a `tests/test_listener.py`:

```python
def test_view_factory_used_for_views():
    fake_view = MagicMock()
    listener = HotkeyListener(tk_root=None, view_factory=lambda: fake_view)
    with patch("phonexi.listener.capture", return_value=MagicMock()), \
         patch.object(listener, "_stream_image"):
        listener._start_capture()
    assert listener._current_window is fake_view


def test_schedule_runs_inline_without_tk():
    listener = HotkeyListener(tk_root=None, view_factory=lambda: MagicMock())
    called = []
    listener._schedule(lambda x: called.append(x), 7)
    assert called == [7]
```

- [ ] **Step 6: Correr y ver fallar**

Run: `python -m pytest tests/test_listener.py -v`
Expected: FAIL — `TypeError`/`AttributeError` (sin `view_factory`/`_schedule`).

- [ ] **Step 7: Refactor `__init__` y agregar `_schedule`**

En `phonexi/listener.py`, reemplazar el `__init__` actual por:

```python
    def __init__(self, tk_root=None, use_primary: bool = False, view_factory=None) -> None:
        self._tk_root = tk_root
        self._use_primary = use_primary
        self._view_factory = view_factory or (
            lambda: ResultWindow(self._tk_root, use_primary=self._use_primary)
        )
        self._pressed: set = set()
        self._lock = threading.Lock()
        self._current_window = None

        self._recording = False
        self._record_stop: threading.Event | None = None
        self._hotkey_cooldown = False
        self._screenshot_cooldown = False
        self._context: Context | None = None

    def _schedule(self, fn, *args) -> None:
        if self._tk_root is not None:
            self._tk_root.after(0, fn, *args)
        else:
            fn(*args)
```

- [ ] **Step 8: Reemplazar `tk_root.after`, creación de ventana y cierre**

En `phonexi/listener.py`, aplicar estos reemplazos exactos:

`_on_press` (rama Escape):
```python
            self._schedule(self._close_current)
```
`_on_screenshot_hotkey`:
```python
    def _on_screenshot_hotkey(self) -> None:
        self._schedule(self._start_capture)
```
`_start_capture` (línea de creación de ventana):
```python
        win = self._view_factory()
```
`_stream_image` (las tres ramas de error):
```python
        except GroqNotConfiguredError:
            self._schedule(win.show_error, "GROQ_API_KEY not set — add it to .env")
        except GroqAPIError as exc:
            self._schedule(win.show_error, f"Groq error: {exc}")
        except Exception as exc:
            self._schedule(win.show_error, f"Error: {exc}")
```
`_on_audio_start`:
```python
        self._schedule(self._open_recording_popup)
```
`_open_recording_popup` (creación de ventana):
```python
        win = self._view_factory()
```
`_record_worker` — reemplazar TODOS los `self._tk_root.after(0, X, ...)` por `self._schedule(X, ...)`:
```python
                self._schedule(win.show_error, f"Audio capture error: {exc}")
```
```python
        self._schedule(win.show_status, "⏳ Analyzing...")
```
```python
                self._schedule(win.show_error, f"Transcription error: {exc}")
```
```python
                self._schedule(win.show_error, "No speech detected")
```
```python
            self._schedule(win.show_status, f"❓ {text}\n")
```
```python
            self._schedule(win.show_error, "GROQ_API_KEY not set — add it to .env")
        except GroqAPIError as exc:
            self._schedule(win.show_error, f"Groq error: {exc}")
        except Exception as exc:
            self._schedule(win.show_error, f"Error: {exc}")
```
`_close_current`:
```python
    def _close_current(self) -> None:
        if self._current_window is not None:
            try:
                self._current_window.close()
            except Exception:
                pass
            self._current_window = None
```

- [ ] **Step 9: Correr toda la suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (incluidos los tests existentes de listener que patchean `phonexi.listener.ResultWindow` — la factory por defecto lo sigue invocando con `(root, use_primary=...)`).

- [ ] **Step 10: Commit**

```bash
git add phonexi/listener.py phonexi/ui.py tests/test_listener.py tests/test_ui.py
git commit -m "refactor: listener uses view_factory + _schedule; ResultWindow.close()"
```

---

### Task 7: Wiring en main.py — modo web + QR

**Files:**
- Modify: `main.py`
- Modify: `requirements.txt`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `WebServer`, `WebView`, `lan_ip` de `phonexi.webserver`; `HotkeyListener(view_factory=...)`.
- Produces: función `main()` que se ramifica según `args.web`; helper `_print_qr(url: str) -> None`.

- [ ] **Step 1: Test que `main()` arranca modo web sin tkinter**

Agregar a `tests/test_main.py`:

```python
from unittest.mock import MagicMock


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
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_main.py::test_main_web_mode_starts_server_and_listener -v`
Expected: FAIL — `main()` aún crea `tk.Tk()` y no usa `WebServer`.

- [ ] **Step 3: Implementar ramas en `main.py`**

Reemplazar la función `main()` actual y agregar helpers. `main.py` queda así (sustituir de `def main()` hacia abajo, dejando intacto `_parse_args` ya extendido en Task 1):

```python
def _print_qr(url: str) -> None:
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)


def _run_web() -> None:
    from phonexi.webserver import WebServer, WebView, lan_ip

    server = WebServer()
    server.start()
    ip = lan_ip()
    url = f"http://{ip}:{server.port}"
    _print_qr(url)
    print(f"[Phonexi] Web mode. Scan the QR or open on your phone (same WiFi):\n"
          f"  {url}\n"
          f"  http://localhost:{server.port}\n"
          "Right Shift + P to capture. Ctrl+C to quit.")

    listener = HotkeyListener(tk_root=None, view_factory=lambda: WebView(server))
    try:
        listener.start()  # blocks on keyboard listener
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")
        server.stop()


def _run_popup(use_primary: bool) -> None:
    root = tk.Tk()
    root.withdraw()

    listener = HotkeyListener(tk_root=root, use_primary=use_primary)
    t = threading.Thread(target=listener.start, daemon=True)
    t.start()

    target = "primary" if use_primary else "secondary"
    print(f"[Phonexi] Running on {target} monitor. "
          "Right Shift + P to capture. Ctrl+C to quit.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")


def main() -> None:
    args = _parse_args()
    if args.web:
        _run_web()
    else:
        _run_popup(args.primary)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Agregar dependencia**

En `requirements.txt`, agregar al final:

```
qrcode>=7.4
```

Instalar: `pip install "qrcode>=7.4"`

- [ ] **Step 5: Correr y ver pasar**

Run: `python -m pytest tests/ -v`
Expected: PASS (toda la suite, incluido el nuevo test de modo web).

- [ ] **Step 6: Commit**

```bash
git add main.py requirements.txt tests/test_main.py
git commit -m "feat: wire web mode in main with QR + LAN URLs"
```

---

### Task 8: Verificación manual y README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Produces: documentación del flag `-w`/`--web`.

- [ ] **Step 1: Verificación manual end-to-end**

Run: `python main.py --web`
Expected:
- Imprime un QR ASCII y dos URLs (`http://<ip-lan>:<puerto>` y `http://localhost:<puerto>`).
- Abrir `http://localhost:<puerto>` en un navegador muestra la página oscura "Waiting for Phonexi...".
- Escanear el QR con el celular (misma WiFi) abre la misma página.
- `RShift+P` sobre una pregunta → la respuesta en markdown con código resaltado aparece en el celular/navegador sin recargar.
- `RAlt+P` (start) → `🎙 Listening...`; `RAlt+P` (stop) → `⏳ Analyzing...`, luego `❓ <pregunta>` y la respuesta.
- `Ctrl+C` detiene limpio.

- [ ] **Step 2: Documentar en README**

En `README.md`, en la tabla de Hotkeys NO cambia nada. Agregar tras la sección `### 4. Run` (después del bloque `python main.py -P`):

```markdown
Serve responses to your **phone** instead of an on-screen popup (useful when
screen-sharing or on a single monitor):

```bash
python main.py -w
```

Phonexi prints a QR code and the LAN URL in the terminal. Scan the QR with your
phone (same WiFi) — responses appear in the browser, auto-updating via SSE.
No popup is shown on the shared screen. The hotkeys are unchanged.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document -w/--web phone output mode"
```

---

## Notas de cierre

- Tras Task 8, usar `superpowers:finishing-a-development-branch` para decidir merge/PR.
- El test HTTP real (`test_webserver_picks_port_and_serves_index`) abre un puerto
  efímero en `127.0.0.1`; si el entorno bloquea sockets, marcarlo `@pytest.mark.skip`
  con razón explícita (no borrarlo).
