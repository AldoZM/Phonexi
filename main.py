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


def _run_web() -> None:
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

    listener = HotkeyListener(tk_root=None, view_factory=lambda: WebView(server))
    try:
        listener.start()  # blocks on keyboard listener
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")
        server.stop()


def _run_popup(use_primary: bool) -> None:
    root = tk.Tk()
    root.withdraw()

    listener = HotkeyListener(tk_root=root, use_primary=use_primary)
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
    if args.web:
        _run_web()
    else:
        _run_popup(args.primary)


if __name__ == "__main__":
    main()
