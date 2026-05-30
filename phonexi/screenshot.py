import mss
import mss.tools
from datetime import datetime
from pathlib import Path


_SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"


def capture() -> Path:
    _SCREENSHOTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = _SCREENSHOTS_DIR / f"capture_{timestamp}.png"

    with mss.mss() as sct:
        monitor = sct.monitors[0]  # full virtual desktop (all monitors)
        screenshot = sct.grab(monitor)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(output_path))

    return output_path
