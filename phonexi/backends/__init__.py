"""Runtime backend selection by platform.

Selecting a backend never imports another platform's OS-specific dependencies:
concrete backend classes import their deps lazily inside their methods, so
get_*_backend("win32") works on Linux (only calling the methods would need
Windows libs) and vice versa.
"""
from __future__ import annotations

import sys


def _resolve(platform: str | None) -> str:
    return platform if platform is not None else sys.platform


def get_audio_backend(platform: str | None = None):
    plat = _resolve(platform)
    if plat == "win32":
        from phonexi.backends.windows import WindowsAudioBackend

        return WindowsAudioBackend()
    if plat.startswith("linux"):
        from phonexi.backends.linux import LinuxAudioBackend

        return LinuxAudioBackend()
    raise RuntimeError(f"Unsupported platform: {plat}")


def get_screenshot_backend(platform: str | None = None):
    plat = _resolve(platform)
    if plat == "win32":
        from phonexi.backends.windows import WindowsScreenshotBackend

        return WindowsScreenshotBackend()
    if plat.startswith("linux"):
        from phonexi.backends.linux import LinuxScreenshotBackend

        return LinuxScreenshotBackend()
    raise RuntimeError(f"Unsupported platform: {plat}")


def get_input_backend(platform: str | None = None):
    plat = _resolve(platform)
    if plat == "win32":
        from phonexi.backends.windows import WindowsInputBackend

        return WindowsInputBackend()
    if plat.startswith("linux"):
        from phonexi.backends.linux import LinuxInputBackend

        return LinuxInputBackend()
    raise RuntimeError(f"Unsupported platform: {plat}")
