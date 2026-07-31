"""Windows backends. Platform deps (pyaudiowpatch, mss, ctypes) are imported
lazily inside methods so this module imports cleanly on any OS."""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

_SCREENSHOTS_DIR = Path(__file__).parent.parent.parent / "screenshots"


class WindowsAudioBackend:
    def record(self, stop_event: threading.Event) -> bytes:
        from phonexi.audio import _record_windows

        return _record_windows(stop_event)


class WindowsScreenshotBackend:
    def start(self) -> None:  # stateless on Windows
        pass

    def stop(self) -> None:
        pass

    def capture(self) -> Path:
        import ctypes
        import ctypes.wintypes

        import mss
        import mss.tools

        def _monitor_at_cursor(monitors: list) -> dict:
            point = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            cx, cy = point.x, point.y
            for mon in monitors[1:]:
                if (mon["left"] <= cx < mon["left"] + mon["width"] and
                        mon["top"] <= cy < mon["top"] + mon["height"]):
                    return mon
            return monitors[1]

        _SCREENSHOTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = _SCREENSHOTS_DIR / f"capture_{timestamp}.png"

        with mss.mss() as sct:
            monitor = _monitor_at_cursor(sct.monitors)
            shot = sct.grab(monitor)
            mss.tools.to_png(shot.rgb, shot.size, output=str(output_path))

        return output_path


class WindowsInputBackend:
    """Global hotkey detection via pynput.

    Right Shift + P -> on_screenshot; Right Alt + P -> on_audio_toggle; Esc -> on_close.
    """

    _TRIGGER_CHAR = "p"
    _P_VK = 80  # 'P' virtual key code (used when AltGr suppresses key.char)

    def run(
        self,
        on_screenshot: Callable[[], None],
        on_audio_toggle: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        from pynput import keyboard

        screenshot_mod = keyboard.Key.shift_r  # Right Shift + P
        audio_mod = keyboard.Key.alt_gr        # Right Alt + P (alt_gr on ES/LA layouts)

        pressed: set = set()
        lock = threading.Lock()
        screenshot_cooldown = False
        audio_cooldown = False

        def is_p(key) -> bool:
            return (
                (hasattr(key, "char") and key.char and key.char.lower() == self._TRIGGER_CHAR)
                or (hasattr(key, "vk") and key.vk == self._P_VK)
            )

        def on_press(key) -> None:
            nonlocal screenshot_cooldown, audio_cooldown
            with lock:
                pressed.add(key)
            if key == keyboard.Key.esc:
                on_close()
                return
            if not is_p(key):
                return
            if screenshot_mod in pressed and not screenshot_cooldown:
                screenshot_cooldown = True
                on_screenshot()
            elif audio_mod in pressed and not audio_cooldown:
                audio_cooldown = True
                on_audio_toggle()

        def on_release(key) -> None:
            nonlocal screenshot_cooldown, audio_cooldown
            with lock:
                pressed.discard(key)
            if key == screenshot_mod:
                screenshot_cooldown = False
            if key == audio_mod:
                audio_cooldown = False

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
