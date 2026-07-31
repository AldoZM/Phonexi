from pathlib import Path

from phonexi import screenshot
from phonexi import backends


def test_screenshot_module_imports_without_windows_deps():
    # Importing must not require mss/ctypes at module load.
    assert hasattr(screenshot, "capture")


def test_capture_delegates_to_selected_backend(monkeypatch):
    class FakeBackend:
        def capture(self):
            return Path("/tmp/fake.png")

    monkeypatch.setattr(screenshot, "get_screenshot_backend", lambda: FakeBackend())

    assert screenshot.capture() == Path("/tmp/fake.png")


def test_get_screenshot_backend_selectable_per_platform():
    assert hasattr(backends.get_screenshot_backend(platform="win32"), "capture")
    assert hasattr(backends.get_screenshot_backend(platform="linux"), "capture")


def test_screenshot_backend_has_lifecycle():
    b = backends.get_screenshot_backend(platform="linux")
    assert hasattr(b, "start")
    assert hasattr(b, "stop")
