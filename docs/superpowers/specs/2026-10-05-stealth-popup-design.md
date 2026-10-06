# Stealth Popup (Anti-Screen Share) — Design

**Date:** 2026-10-05  
**Status:** Draft / Review  

## Problem

When sharing a screen during technical interviews or video calls (Google Meet, Microsoft Teams, Zoom, Discord, OBS), the on-screen Phonexi popup window (`ResultWindow`) is visible to interviewers and stream viewers.

The user needs the popup to be **invisible during screen sharing and screen recording**, while remaining completely visible, legible, and interactive on their physical monitor.

## Solution: Win32 Display Affinity

Windows 10 (version 2004, build 19041+) and Windows 11 provide the API `SetWindowDisplayAffinity`:
```c
BOOL SetWindowDisplayAffinity(HWND hWnd, DWORD dwAffinity);
```

Affinity modes:
- `WDA_NONE` (`0x00000000`): Normal rendering; captured by all tools.
- `WDA_MONITOR` (`0x00000001`): Rendered only on monitor; capture tools see black box.
- `WDA_EXCLUDEFROMCAPTURE` (`0x00000011`): Window is excluded from all capture APIs (Desktop Duplication, Windows Graphics Capture, BitBlt, PrintWindow). The desktop or windows behind it are rendered instead.

### Tkinter Window Handle Gotcha
In Tkinter on Windows, `window.winfo_id()` returns the handle of the internal Tk container window (child control). Calling `SetWindowDisplayAffinity` directly on this handle fails with `ERROR_INVALID_PARAMETER` (87) because the API requires a top-level window.
The actual top-level OS `HWND` is obtained via:
```python
ga_root = 2  # GA_ROOT
top_hwnd = user32.GetAncestor(hwnd, ga_root) or hwnd
```

## Behavior

| Setting / Flag | Physical Monitor | Screen Share (Meet/Teams/Zoom/Discord/OBS) |
|---|---|---|
| Default (`STEALTH_MODE=1` or no flag) | Popup visible & interactive | **Invisible (shows background)** |
| `--no-stealth` or `STEALTH_MODE=0` | Popup visible & interactive | Popup visible in share |

## Changes

### 1. `phonexi/config.py`
- Add `STEALTH_MODE: bool = os.getenv("STEALTH_MODE", "1") != "0"` (default `True`).

### 2. `phonexi/ui.py`
- Add helper function `set_window_stealth(window: tk.Toplevel | tk.Tk, enable: bool = True) -> bool`:
  - Platform check (`sys.platform == "win32"`).
  - Obtains `HWND` and top-level root window using `GetAncestor(hwnd, GA_ROOT)`.
  - Sets `WDA_EXCLUDEFROMCAPTURE` (`0x11`) with fallback to `WDA_MONITOR` (`0x01`).
  - Allows `enable=False` to restore `WDA_NONE` (`0x00`).
- Update `ResultWindow.__init__(self, root: tk.Tk, use_primary: bool = False, stealth: bool | None = None)`:
  - Resolves `self._stealth = STEALTH_MODE if stealth is None else stealth`.
  - Calls `self._apply_display_affinity()` on window initialization.

### 3. `main.py`
- Add `--no-stealth` CLI flag in `_parse_args()`.
- Pass `stealth=not args.no_stealth` to `_run_popup`.
- When `stealth=False`, provide a `view_factory` that sets `stealth=False`.

### 4. `README.md`
- Document screen-share protection feature and `--no-stealth` / `STEALTH_MODE` options.

## Out of Scope
- Web mode (`-w`): Already serves responses over LAN to phone; nothing is rendered on screen.
- Non-Windows platforms: Graceful no-op.

## Testing
- Verify `SetWindowDisplayAffinity` is called with `0x11` when stealth is active.
- Verify `stealth=False` does not set capture exclusion.
- Fallback verification if `0x11` fails.
- Non-Windows platform safety check.
