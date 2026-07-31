"""End-to-end: capture a screenshot, send it to Groq, print the answer.

Proves the full Linux chain minus the hotkey (screenshot backend -> processor).
Run:  .venv/bin/python scripts/diag_e2e.py
A portal consent dialog appears once — pick the monitor showing a question.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from phonexi.backends.linux import LinuxScreenshotBackend
from phonexi.processor import process


def main() -> None:
    b = LinuxScreenshotBackend()
    b.start()
    try:
        path = b.capture()
        print(f"[capture] {path}", flush=True)
        print("[groq] streaming answer:\n", flush=True)
        for token in process(path):
            print(token, end="", flush=True)
        print("\n\n[done]", flush=True)
    finally:
        b.stop()


if __name__ == "__main__":
    main()
