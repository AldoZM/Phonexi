import threading
from pynput import keyboard

from phonexi.processor import ModelNotFoundError, OllamaNotRunningError, process
from phonexi.screenshot import capture
from phonexi.ui import ResultWindow


class HotkeyListener:
    _TRIGGER_KEY = keyboard.KeyCode.from_char("p")
    _MODIFIER_KEY = keyboard.Key.shift_r

    def __init__(self, tk_root) -> None:
        self._tk_root = tk_root
        self._pressed: set = set()
        self._lock = threading.Lock()
        self._current_window = None

    def _on_press(self, key) -> None:
        with self._lock:
            self._pressed.add(key)

        if (
            self._MODIFIER_KEY in self._pressed
            and self._TRIGGER_KEY in self._pressed
        ):
            self._on_hotkey()

    def _on_release(self, key) -> None:
        with self._lock:
            self._pressed.discard(key)

    def _on_hotkey(self) -> None:
        threading.Thread(target=self._process_and_show, daemon=True).start()

    def _process_and_show(self) -> None:
        # Close any existing window before opening a new one
        if self._current_window is not None:
            try:
                self._tk_root.after(0, self._current_window._win.destroy)
            except Exception:
                pass

        path = capture()
        win = ResultWindow(self._tk_root)
        self._current_window = win
        try:
            tokens = process(path)
            win.show(tokens)
        except OllamaNotRunningError:
            win.show_error("Ollama not running — start with: ollama serve")
        except ModelNotFoundError:
            win.show_error("Model not found — run: ollama pull llama3.2-vision:11b")

    def start(self) -> None:
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
