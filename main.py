"""Phonexi entry point."""

import argparse
import threading
import tkinter as tk

from phonexi.briefing import ALLOWED_SUFFIXES, BriefingError
from phonexi.briefing import load as load_briefing
from phonexi.engines import get_engine
from phonexi.engines import installed as installed_clis
from phonexi.listener import HotkeyListener
from phonexi.picker import PickerUnavailableError, choose
from phonexi.providers import (
    activate,
    available_models,
    default_selection,
    key_order,
    selection_for,
)
from phonexi.screenshot import DEFAULT_REGION, parse_region, prune

EPILOG = """Examples:
  python main.py                      popup on the secondary monitor
  python main.py -model               pick the model with the arrow keys first
  python main.py -cli                 answer with a local CLI (Claude Code / Antigravity)
  python main.py -c contexts/me.md    answer with a prior-context file
  python main.py -r 1600x900 -P       capture a box around the cursor, popup on primary
  python main.py -w                   read answers on your phone instead

Hotkeys:
  Right Shift + P    capture the screen and answer
  Right Alt + P      start / stop listening to the call audio

Settings in .env:
  GROQ_API_KEY, GEMINI_API_KEY   the key written highest picks the default provider
  GROQ_MODEL_TEXT, GROQ_MODEL_VISION, GEMINI_MODEL   default models
  GROQ_MAX_TOKENS, GEMINI_MAX_TOKENS                 answer length cap
  GROQ_REASONING_TEXT, GROQ_REASONING_VISION, GEMINI_REASONING   thinking budget
  AGY_EFFORT                     reasoning budget for -cli agy (default high)
  Audio is always transcribed by Groq Whisper, so it needs GROQ_API_KEY --
  that holds with -cli too, since neither CLI processes audio.
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phonexi interview assistant.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    # Declared by hand so the single-dash long spellings work too: without
    # it argparse would read -help as -h and -model as -m with "odel".
    parser.add_argument(
        "-h", "-help", "--help",
        action="help",
        help="Show this help and exit.",
    )
    parser.add_argument(
        "-m", "-model", "--model",
        action="store_true",
        help="Choose the model with the arrow keys before starting. Without it "
             "the provider whose key is written highest in .env is used.",
    )
    parser.add_argument(
        "-cli", "--cli",
        action="store_true",
        help="Answer with a local CLI instead of the API, using the subscription "
             "already paid for. Opens the same arrow-key picker as -model, "
             "listing the CLIs installed on this machine.",
    )
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
        "-r", "--region",
        nargs="?",
        const=f"{DEFAULT_REGION[0]}x{DEFAULT_REGION[1]}",
        default=None,
        metavar="WIDTHxHEIGHT",
        help="Capture a box around the cursor instead of the whole monitor "
             f"(default {DEFAULT_REGION[0]}x{DEFAULT_REGION[1]}). Keep it 16:9: "
             "Groq prices an image by aspect ratio, and other shapes cost more.",
    )
    parser.add_argument(
        "-c", "--context",
        metavar="FILE",
        default=None,
        help=f"Path to a prior-context file ({' or '.join(ALLOWED_SUFFIXES)}) read at "
             "startup so answers come out oriented instead of cold.",
    )
    args = parser.parse_args()
    if args.cli and args.model:
        parser.error("-model picks an API model and -cli picks a local CLI; "
                     "they answer the same question, so pass only one.")
    if args.region is not None:
        try:
            args.region = parse_region(args.region)
        except ValueError as exc:
            parser.error(f"--region: {exc}")
    return args


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


def _choose_cli():
    """Pick the local CLI that answers, with the same picker -model uses.

    Only what shutil.which() finds is listed, and the choice is made before any
    hotkey is registered: a missing CLI must fail at startup, not mid-interview.
    """
    found = installed_clis()
    if not found:
        print("[Phonexi] -cli found no CLI installed. Install Claude Code "
              "(npm i -g @anthropic-ai/claude-code) or Antigravity, or drop the flag.")
        raise SystemExit(1)
    try:
        chosen = choose(found, what="CLI")
    except PickerUnavailableError:
        print("[Phonexi] -cli needs an interactive terminal; run Phonexi from a console.")
        raise SystemExit(1)
    if chosen is None:
        print("[Phonexi] Cancelled.")
        raise SystemExit(0)
    engine = get_engine(chosen.name)
    print(f"[Phonexi] Using {engine.LABEL} ({chosen.name}). "
          "Audio still goes through Groq Whisper.")
    return engine


def _run_web(briefing: "str | None" = None, region: "tuple | None" = None,
             engine=None) -> None:
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
        region=region,
        engine=engine,
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


def _run_popup(use_primary: bool, briefing: "str | None" = None,
               region: "tuple | None" = None, engine=None) -> None:
    root = tk.Tk()
    root.withdraw()

    listener = HotkeyListener(
        tk_root=root,
        use_primary=use_primary,
        briefing=briefing,
        region=region,
        engine=engine,
    )
    t = threading.Thread(target=listener.start, daemon=True)
    t.start()

    # mainloop() blocks inside Tcl's event loop, where Python never reaches a
    # bytecode boundary and so never runs its SIGINT handler. A no-op tick hands
    # control back often enough for Ctrl+C to raise on its own — without it the
    # interrupt waits for a Tk event, which is why quitting needed an Escape
    # after the Ctrl+C. Same reason _run_web polls instead of blocking on join.
    def _tick() -> None:
        root.after(200, _tick)

    root.after(200, _tick)

    target = "primary" if use_primary else "secondary"
    print(f"[Phonexi] Running on {target} monitor. "
          "Right Shift + P to capture. Ctrl+C to quit.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def _choose_provider(pick: bool) -> None:
    """Activate the model to answer with — picked by hand, or the top key's."""
    order = key_order()
    default = default_selection(order)
    if pick:
        models = available_models(order)
        start = next((i for i, m in enumerate(models)
                      if m.provider == default.provider
                      and m.name in (default.text_model, default.vision_model)), 0)
        try:
            chosen = choose(models, start=start)
        except PickerUnavailableError as exc:
            print(f"[Phonexi] {exc}")
            raise SystemExit(1)
        if chosen is None:
            print("[Phonexi] Cancelled.")
            raise SystemExit(0)
        selection = selection_for(chosen)
    else:
        selection = default
    activate(selection)
    if selection.text_model == selection.vision_model:
        print(f"[Phonexi] Using {selection.provider}: {selection.text_model}")
    else:
        print(f"[Phonexi] Using {selection.provider}: {selection.text_model} (text), "
              f"{selection.vision_model} (captures)")


def main() -> None:
    args = _parse_args()
    if args.cli:
        # transcribe() builds its own Groq client with its own key, so the API
        # model selection would never be read — announcing it only misleads.
        engine = _choose_cli()
    else:
        engine = None
        _choose_provider(args.model)
    briefing = _read_context(args.context)
    prune()
    if args.region:
        print(f"[Phonexi] Region mode: {args.region[0]}x{args.region[1]} around the cursor.")
    if args.web:
        _run_web(briefing, args.region, engine)
    else:
        _run_popup(args.primary, briefing, args.region, engine)


if __name__ == "__main__":
    main()
