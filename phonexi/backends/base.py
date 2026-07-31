"""Platform backend interfaces.

Each backend isolates the OS-specific parts of Phonexi so the rest of the app
(listener orchestration, UI, webserver, processor) stays platform-neutral.
Concrete backends live in windows.py and linux.py; the selector in __init__.py
picks one at runtime by sys.platform.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class AudioBackend(Protocol):
    def record(self, stop_event: threading.Event) -> bytes:
        """Capture system audio until stop_event is set. Return WAV bytes."""
        ...


@runtime_checkable
class ScreenshotBackend(Protocol):
    def start(self) -> None:
        """One-time setup (Linux: negotiate ScreenCast session). No-op on Windows."""
        ...

    def capture(self) -> Path:
        """Grab the current screen and return the path to a saved PNG."""
        ...

    def stop(self) -> None:
        """Release capture resources. No-op on Windows."""
        ...


@runtime_checkable
class InputBackend(Protocol):
    def run(
        self,
        on_screenshot: Callable[[], None],
        on_audio_toggle: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        """Listen for the global hotkeys and invoke the matching callback.

        Blocks until the listener stops. Debouncing of held keys is the
        backend's responsibility; deciding start-vs-stop for audio is the
        caller's (on_audio_toggle fires once per Right Alt + P press).
        """
        ...
