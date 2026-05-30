import threading
from pynput import keyboard
from phonexi.screenshot import capture


class HotkeyListener:
    """Listens for Right Shift + P and triggers a screenshot."""

    _TRIGGER_KEY = keyboard.KeyCode.from_char("p")
    _MODIFIER_KEY = keyboard.Key.shift_r

    def __init__(self) -> None:
        self._pressed: set = set()
        self._lock = threading.Lock()

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
        # Run in thread so listener loop doesn't block
        threading.Thread(target=self._capture_and_log, daemon=True).start()

    def _capture_and_log(self) -> None:
        path = capture()
        print(f"[Phonexi] Screenshot saved → {path}")

    def start(self) -> None:
        """Block until listener stops (Ctrl+C to exit)."""
        print("[Phonexi] Running. Press Right Shift + P to capture. Ctrl+C to quit.")
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
