# Linux Port — Design

**Date:** 2026-07-30
**Status:** Approved (design), pending implementation plan

## Goal

Make Phonexi run fully on Linux (all three features: hotkeys, screenshot, audio),
targeting Ubuntu GNOME on **Wayland**, without breaking the existing Windows build.

Development/test machine: Ubuntu GNOME Shell 50.1, Wayland session, PipeWire audio,
Python 3.14. This is the reference Linux target.

## Why this is non-trivial (Wayland constraints)

Wayland deliberately blocks three things the current Windows code relies on:

1. **Global keyboard capture** — apps cannot listen to global keys. `pynput`'s global
   listener does not work under a native Wayland session.
2. **Global cursor position** — apps cannot query the pointer location. The current
   `screenshot.py` picks the monitor under the cursor via `ctypes.windll.user32.GetCursorPos`;
   there is no Wayland equivalent available to an unprivileged app.
3. **Discreet screenshots** — `org.gnome.Shell.Screenshot.Screenshot` returns
   `AccessDenied` on GNOME 50.1 for non-shell callers (verified on target machine).
   The XDG portal `Screenshot` shows a flash/indicator on every capture, which breaks the
   product's core requirement of being discreet.

## Chosen approach

A **platform-backend abstraction layer**. Platform-specific work moves behind interfaces
selected at runtime by `sys.platform`. Windows keeps its existing implementation verbatim;
Linux is a new backend. View/UI/webserver/processor/config are untouched.

### Decisions (locked)

- **Input:** evdev (`/dev/input/event*`). Works under both Wayland and X11, gives real
  global key capture. Requires the user to be in the `input` group
  (`sudo usermod -aG input <user>` + re-login). Keeps the same physical hotkeys
  (Right Shift + P, Right Alt + P).
- **Screenshot:** XDG Desktop Portal **ScreenCast** + **PipeWire** via GStreamer
  (`pipewiresrc`). One consent dialog when the Phonexi daemon starts (the user picks which
  monitor to share); every subsequent `Right Shift + P` grabs the latest frame from the
  live PipeWire stream **silently, no further dialogs**. This is the only discreet path on
  modern GNOME Wayland. It also removes the cursor-position dependency — the captured
  monitor is fixed at consent time. GStreamer via PyGObject (`gi`) is already present on the
  target machine.
- **Audio:** PipeWire monitor capture. Record the `.monitor` of the default sink (captures
  system audio = the interviewer on a call, not the mic — same intent as the Windows WASAPI
  loopback). Implemented via `pw-record` (subprocess) with GStreamer `pipewiresrc` as a
  fallback option. Reuses the existing `_to_mono_16k()` and `transcribe()` (Groq),
  which are already platform-neutral.

## File structure

Windows code stays; Linux enters via runtime selection.

```
phonexi/
  backends/
    __init__.py     # get_input_backend() / get_screenshot_backend() / get_audio_backend()
                    #   -> dispatch on sys.platform ("win32" vs "linux")
    base.py         # Protocols: InputBackend, ScreenshotBackend, AudioBackend
    windows.py      # wraps existing code: mss+ctypes screenshot, WASAPI audio, pynput input
    linux.py        # evdev input, ScreenCast-portal+GStreamer screenshot, PipeWire audio
  screenshot.py     # capture() -> delegates to screenshot backend
  audio.py          # record() -> delegates to audio backend; transcribe() unchanged (Groq)
  listener.py       # uses the input backend instead of pynput directly
  ui.py             # unchanged (Tkinter runs on Linux via XWayland)
  webserver.py      # unchanged (stdlib http.server + SSE — already cross-platform)
  processor.py      # unchanged
  config.py         # unchanged
```

### Interface contracts (`base.py`)

- `InputBackend`: given callbacks for the two hotkeys (screenshot trigger, audio toggle)
  and the Escape/close action, runs a listen loop. Same event semantics the current
  `HotkeyListener` expects, so `listener.py`'s orchestration logic is unchanged.
- `ScreenshotBackend`: `start()` (Linux: negotiate ScreenCast session + open PipeWire
  stream, one-time consent), `capture() -> Path` (grab latest frame, save PNG), `stop()`.
  Windows `start()`/`stop()` are no-ops.
- `AudioBackend`: `record(stop_event: threading.Event) -> bytes` returning WAV bytes,
  matching the current `audio.record()` signature.

## Dependencies

Split requirements so Windows never pulls evdev and Linux never pulls `pyaudiowpatch`:

- `requirements.txt` — shared: `groq`, `pygments`, `python-dotenv`, `qrcode`, `pytest`.
- `requirements-windows.txt` — `mss`, `pynput`, `pyaudiowpatch`.
- `requirements-linux.txt` — `evdev`, `PyGObject` (+ system GStreamer:
  `gir1.2-gst-plugins-base-1.0`, `gstreamer1.0-pipewire`).

`mss` and `pynput` become Windows-only; `linux.py` must not import them at module load.
Backends import their platform deps lazily inside `get_*_backend()` so importing the wrong
platform's module never crashes.

## Testing

- Current tests assume Windows (`pyaudiowpatch`, ctypes). Refactor so tests target the
  backend interfaces with mocks, not concrete platform modules.
- Platform-neutral units stay directly tested: `_to_mono_16k()`, `_parse_args()`,
  webserver (`Broadcaster`, `format_sse`, `lan_ip`, `find_free_port`), `_print_qr`.
- New tests: backend selection by `sys.platform`; Linux backends behind mocks
  (fake evdev events, fake PipeWire frame, fake portal session).
- Run the full suite on the Linux target machine.

## Build order (incremental, each independently verifiable)

1. **Backend layer + selector** — refactor; Windows path still passes its tests.
2. **Audio (Linux/PipeWire)** — easiest to verify (play audio, record, transcribe).
3. **Input (Linux/evdev)** — needs `input` group membership.
4. **Screenshot (Linux/ScreenCast+GStreamer)** — heaviest; portal negotiation + PipeWire.

## Risks / open items

- `input` group membership requires a re-login before evdev works.
- ScreenCast consent does not persist across daemon restarts — GNOME re-prompts each launch
  (acceptable: one dialog at startup, silent thereafter).
- GStreamer needs system packages beyond pip (`gir1.2-gst-*`, `gstreamer1.0-pipewire`).
- Tkinter popup renders via XWayland; multi-monitor placement may differ from Windows —
  verify `_target_monitor()` behavior on the Linux target.
- Verified against GNOME 50.1 specifically; other compositors (KDE, wlroots) are out of
  scope for this pass but the portal path should generalize.
