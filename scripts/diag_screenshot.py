"""Verbose live diagnostic for the Linux ScreenCast screenshot backend.

Run:  .venv/bin/python scripts/diag_screenshot.py
A portal consent dialog appears once — pick a monitor and click Share.
Prints each stage so we can see exactly where it fails.
"""
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from phonexi.backends.linux import LinuxScreenshotBackend


def main() -> None:
    b = LinuxScreenshotBackend()
    try:
        print("[1] start(): negotiating ScreenCast portal (consent dialog)...", flush=True)
        b.start()
        print("[2] start() OK — pipeline PLAYING", flush=True)

        print("[3] capture(): pulling frame...", flush=True)
        path = b.capture()
        print(f"[4] capture() returned: {path}", flush=True)

        exists = path.exists()
        size = path.stat().st_size if exists else 0
        print(f"[5] file exists={exists} size={size} bytes", flush=True)
    except Exception:
        print("[X] ERROR:", flush=True)
        traceback.print_exc()
    finally:
        b.stop()
        print("[6] stop() done", flush=True)


if __name__ == "__main__":
    main()
