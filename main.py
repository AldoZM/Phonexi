"""Phonexi entry point."""

import argparse
import threading
import tkinter as tk

from phonexi.briefing import ALLOWED_SUFFIXES, BriefingError
from phonexi.briefing import load as load_briefing
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
    parser.add_argument(
        "-c", "--context",
        metavar="FILE",
        default=None,
        help=f"Path to a prior-context file ({' or '.join(ALLOWED_SUFFIXES)}) read at "
             "startup so answers come out oriented instead of cold.",
    )
    return parser.parse_args()


def _print_qr(url: str) -> None:
    import sys
    import qrcode
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)


def _read_context(path: "str | None") -> "str | None":
    """Read the context file up front — an unusable one aborts before any hotkey."""
    if path is None:
        return None
    try:
        text = load_briefing(path)
    except BriefingError as exc:
        print(f"[Phonexi] Context file error: {exc}")
        raise SystemExit(1)
    print(f"[Phonexi] Context loaded from {path} ({len(text)} characters).")
    return text


def _run_web(briefing: "str | None" = None) -> None:
    from phonexi.webserver import WebServer, WebView, lan_ip

    server = WebServer()
    server.start()
    ip = lan_ip()
    url = f"http://{ip}:{server.port}"
    _print_qr(url)
    print(f"[Phonexi] Web mode. Scan the QR or open on your phone (same WiFi):\n"
          f"  {url}\n"
          f"  http://localhost:{server.port}\n"
          "Right Shift + P to capture. Ctrl+C to quit.")

    # Run the keyboard listener on a daemon thread and block the main thread on
    # an interruptible join loop — a bare listener.join() on the main thread is
    # not interruptible by Ctrl+C on Windows, so the process wouldn't quit.
    listener = HotkeyListener(
        tk_root=None,
        view_factory=lambda: WebView(server),
        briefing=briefing,
    )
    t = threading.Thread(target=listener.start, daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")
    finally:
        server.stop()


def _run_popup(use_primary: bool, briefing: "str | None" = None) -> None:
    root = tk.Tk()
    root.withdraw()

    listener = HotkeyListener(
        tk_root=root,
        use_primary=use_primary,
        briefing=briefing,
    )
    t = threading.Thread(target=listener.start, daemon=True)
    t.start()

    target = "primary" if use_primary else "secondary"
    print(f"[Phonexi] Running on {target} monitor. "
          "Right Shift + P to capture. Ctrl+C to quit.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")


def main() -> None:
    args = _parse_args()
    briefing = _read_context(args.context)
    if args.web:
        _run_web(briefing)
    else:
        _run_popup(args.primary, briefing)


if __name__ == "__main__":
    main()
