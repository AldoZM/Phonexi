# Monitor Selector — Design

**Date:** 2026-06-11
**Status:** Approved

## Problem

The result popup always renders on the auto-detected secondary monitor
(`ResultWindow._secondary_monitor()`). The user wants to choose, at startup,
whether the popup appears on the **primary** monitor instead — controlled by a
command-line flag.

## Behavior

| Command | Popup monitor |
|---------|---------------|
| `python main.py -P` / `--primary` | Primary monitor |
| `python main.py` (no flag) | Secondary monitor (current behavior) |

Scope is intentionally limited to a primary/secondary toggle for a 2-monitor
setup. No per-index targeting (`--monitor N`) — YAGNI for now.

## Changes

### `main.py`
- Add `argparse` with a single boolean flag `-P` / `--primary`.
- Pass the parsed value as `use_primary` into `HotkeyListener`.

### `phonexi/listener.py`
- `HotkeyListener.__init__(self, tk_root, use_primary: bool = False)` — store flag.
- Forward `use_primary` to every `ResultWindow(...)` construction:
  - `_start_capture` (screenshot flow)
  - `_open_recording_popup` (audio flow)

### `phonexi/ui.py`
- `ResultWindow.__init__(self, root, use_primary: bool = False)` — store flag.
- Replace `_secondary_monitor()` with `_target_monitor()`:
  - `use_primary=True` → return the monitor with `is_primary=True`.
  - `use_primary=False` → first non-primary monitor (existing logic).
  - Fallback: if no matching monitor exists (single-display machine), return the
    first real monitor (`monitors[1]` equivalent) so the popup still shows.

## Out of scope / untouched

- Hotkeys, capture orchestration, audio flow.
- `screenshot.py` `_monitor_at_cursor` — screenshot still captures the monitor
  under the cursor, independent of where the popup renders.

## Testing

`tests/`:
- `_target_monitor()` returns the primary monitor when `use_primary=True` and the
  secondary when `use_primary=False`, using a mocked `mss` monitor list.
- Single-monitor fallback returns a valid monitor in both modes.
- CLI parsing: `-P`/`--primary` sets the flag true; absence leaves it false.
