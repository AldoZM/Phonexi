import threading
from pynput import keyboard

from phonexi.processor import ModelNotFoundError, OllamaNotRunningError, process
from phonexi.screenshot import capture
from phonexi.ui import ResultWindow


class HotkeyListener:
    _TRIGGER_CHAR = "p"
    _MODIFIER_KEY = keyboard.Key.shift_r

    def __init__(self, tk_root) -> None:
        self._tk_root = tk_root
        self._pressed: set = set()
        self._lock = threading.Lock()
        self._current_window = None

    def _on_press(self, key) -> None:
        with self._lock:
            self._pressed.add(key)

        p_down = any(
            hasattr(k, "char") and k.char and k.char.lower() == self._TRIGGER_CHAR
            for k in self._pressed
        )
        if self._MODIFIER_KEY in self._pressed and p_down:
            self._on_hotkey()

    def _on_release(self, key) -> None:
        with self._lock:
            self._pressed.discard(key)

    def _on_hotkey(self) -> None:
        # Schedule capture on main thread so Tkinter widget creation is safe
        self._tk_root.after(0, self._start_capture)

    def _start_capture(self) -> None:
        # Runs on main thread — safe to create/destroy Tk widgets
        if self._current_window is not None:
            try:
                self._current_window._win.destroy()
            except Exception:
                pass

        path = capture()
        win = ResultWindow(self._tk_root)
        self._current_window = win
        threading.Thread(target=self._stream_to, args=(path, win), daemon=True).start()

    def _stream_to(self, path, win) -> None:
        try:
            tokens = process(path)
            win.show(tokens)
        except OllamaNotRunningError:
            self._tk_root.after(0, win.show_error,
                                "Ollama not running — start with: ollama serve")
        except ModelNotFoundError:
            self._tk_root.after(0, win.show_error,
                                "Model not found — run: ollama pull llama3.2-vision:11b")

    def start(self) -> None:
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
