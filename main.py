"""Phonexi entry point."""

import threading
import tkinter as tk

from phonexi.listener import HotkeyListener


def main() -> None:
    root = tk.Tk()
    root.withdraw()

    listener = HotkeyListener(tk_root=root)
    t = threading.Thread(target=listener.start, daemon=True)
    t.start()

    print("[Phonexi] Running. Press Right Shift + P to capture. Ctrl+C to quit.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")


if __name__ == "__main__":
    main()
