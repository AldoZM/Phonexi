import json
import queue
import socket
import threading
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
