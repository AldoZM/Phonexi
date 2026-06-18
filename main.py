"""Phonexi entry point."""

import argparse
import threading
import tkinter as tk

from phonexi.listener import HotkeyListener


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phonexi interview assistant.")
    parser.add_argument(
        "-P", "--primary",
        action="store_true",
        help="Show the popup on the primary monitor (default: secondary).",
    )
    parser.add_argument(
        "-w", "--web",
        action="store_true",
        help="Serve responses on a local web server (read on your phone via QR) "
             "instead of the on-screen popup.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    root = tk.Tk()
    root.withdraw()

    listener = HotkeyListener(tk_root=root, use_primary=args.primary)
    t = threading.Thread(target=listener.start, daemon=True)
    t.start()

    target = "primary" if args.primary else "secondary"
    print(f"[Phonexi] Running on {target} monitor. "
          "Right Shift + P to capture. Ctrl+C to quit.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")


if __name__ == "__main__":
    main()
