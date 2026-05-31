import ctypes
import ctypes.wintypes
import mss
import mss.tools
from datetime import datetime
from pathlib import Path


_SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"


def _monitor_at_cursor(monitors: list) -> dict:
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    cx, cy = point.x, point.y
    for mon in monitors[1:]:
        if (mon["left"] <= cx < mon["left"] + mon["width"] and
                mon["top"] <= cy < mon["top"] + mon["height"]):
            return mon
    return monitors[1]


def capture() -> Path:
    _SCREENSHOTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = _SCREENSHOTS_DIR / f"capture_{timestamp}.png"

    with mss.mss() as sct:
        monitor = _monitor_at_cursor(sct.monitors)
        screenshot = sct.grab(monitor)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(output_path))

    return output_path
