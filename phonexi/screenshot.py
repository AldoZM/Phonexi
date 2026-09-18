import ctypes
import ctypes.wintypes
import re
import mss
import mss.tools
from datetime import datetime
from pathlib import Path


_SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"

# Region captures are built at 16:9 and never at any other shape. Groq bills an
# image by its aspect ratio, not its pixel count: 16:9 costs 783 input tokens at
# every size, while a 4:3 or square crop of the same content costs 1807. Shrink
# a region to fit and you change its ratio, so the box shifts instead.
DEFAULT_REGION = (1280, 720)

_REGION_PATTERN = re.compile(r"^(\d+)[xX](\d+)$")


def parse_region(value: str) -> tuple:
    """Read a WIDTHxHEIGHT flag value into a size pair."""
    match = _REGION_PATTERN.match(value.strip())
    if not match:
        raise ValueError(f"expected WIDTHxHEIGHT (e.g. 1280x720), got {value!r}")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError(f"both sides must be positive, got {value!r}")
    return width, height


def _cursor_pos() -> tuple:
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _monitor_at_cursor(monitors: list, cursor: tuple = None) -> dict:
    cx, cy = _cursor_pos() if cursor is None else cursor
    for mon in monitors[1:]:
        if (mon["left"] <= cx < mon["left"] + mon["width"] and
                mon["top"] <= cy < mon["top"] + mon["height"]):
            return mon
    return monitors[1]


def _region_box(monitor: dict, cursor: tuple, size: tuple) -> dict:
    """A box of `size` centred on the cursor, kept inside the monitor.

    Near an edge the box slides inward rather than shrinking, so the aspect
    ratio — and therefore the token cost — is the same wherever the cursor is.
    A box too large for the monitor gives up and returns the whole monitor.
    """
    width, height = size
    if width > monitor["width"] or height > monitor["height"]:
        return dict(monitor)

    cx, cy = cursor
    left = cx - width // 2
    top = cy - height // 2
    left = max(monitor["left"], min(left, monitor["left"] + monitor["width"] - width))
    top = max(monitor["top"], min(top, monitor["top"] + monitor["height"] - height))
    return {"left": left, "top": top, "width": width, "height": height}


def prune(keep: int = 20, directory: Path = None) -> None:
    """Drop all but the newest `keep` captures.

    Nothing downstream reads an old capture, so the folder is a cache that
    otherwise grows without limit — it had reached 88 MB before this existed.
    """
    directory = _SCREENSHOTS_DIR if directory is None else directory
    if not directory.is_dir():
        return
    shots = sorted(directory.glob("*.png"), key=lambda p: p.stat().st_mtime)
    for old in shots[:-keep] if keep else shots:
        try:
            old.unlink()
        except OSError:
            pass


def capture(region: tuple = None) -> Path:
    """Grab the monitor under the cursor, or a `region`-sized box around it."""
    _SCREENSHOTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = _SCREENSHOTS_DIR / f"capture_{timestamp}.png"

    with mss.mss() as sct:
        # One cursor read for both the monitor pick and the box, so a mouse
        # moved between the two cannot land the box on the wrong screen.
        cursor = _cursor_pos()
        monitor = _monitor_at_cursor(sct.monitors, cursor)
        area = monitor if region is None else _region_box(monitor, cursor, region)
        screenshot = sct.grab(area)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(output_path))

    return output_path
