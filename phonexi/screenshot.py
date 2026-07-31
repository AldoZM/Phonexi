from pathlib import Path

from phonexi.backends import get_screenshot_backend


def capture() -> Path:
    """Capture the current screen and return the path to a saved PNG.

    Delegates to the platform screenshot backend.
    """
    return get_screenshot_backend().capture()
