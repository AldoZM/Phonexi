# Monitor Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `-P`/`--primary` startup flag that renders the result popup on the primary monitor instead of the default secondary monitor.

**Architecture:** A boolean `use_primary` flows from `main.py` (parsed via `argparse`) into `HotkeyListener`, which forwards it to each `ResultWindow`. `ResultWindow` picks its target monitor based on the flag.

**Tech Stack:** Python 3.13, tkinter, mss, pytest. Run tests with `python3.13.exe -m pytest`.

---

## File Structure

- `phonexi/ui.py` — `ResultWindow` gains `use_primary` param; `_secondary_monitor()` becomes `_target_monitor()`.
- `phonexi/listener.py` — `HotkeyListener` gains `use_primary` param, forwards to both `ResultWindow(...)` calls.
- `main.py` — parses `-P`/`--primary`, passes to `HotkeyListener`.
- `tests/test_ui.py` — monitor selection tests.
- `tests/test_listener.py` — forwarding test + fix existing assertion.

---

### Task 1: `ResultWindow` monitor selection

**Files:**
- Modify: `phonexi/ui.py:22` (`__init__` signature), `phonexi/ui.py:52` (call site), `phonexi/ui.py:88-94` (`_secondary_monitor`)
- Test: `tests/test_ui.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ui.py`:

```python
from unittest.mock import patch

_VIRTUAL   = {"left": 0, "top": 0, "width": 100, "height": 100}
_PRIMARY   = {"left": 0, "top": 0, "width": 1920, "height": 1080, "is_primary": True}
_SECONDARY = {"left": 1920, "top": 0, "width": 1920, "height": 1080, "is_primary": False}


def _patch_monitors(monitors):
    p = patch("phonexi.ui.mss.MSS")
    mock = p.start()
    mock.return_value.__enter__.return_value.monitors = monitors
    return p


def test_target_monitor_primary(root):
    p = _patch_monitors([_VIRTUAL, _PRIMARY, _SECONDARY])
    try:
        win = ResultWindow(root, use_primary=True)
        assert win._target_monitor() == _PRIMARY
        win._win.destroy()
    finally:
        p.stop()


def test_target_monitor_secondary_default(root):
    p = _patch_monitors([_VIRTUAL, _PRIMARY, _SECONDARY])
    try:
        win = ResultWindow(root)
        assert win._target_monitor() == _SECONDARY
        win._win.destroy()
    finally:
        p.stop()


def test_target_monitor_single_display_fallback(root):
    p = _patch_monitors([_VIRTUAL, _PRIMARY])
    try:
        win = ResultWindow(root, use_primary=False)
        assert win._target_monitor() == _PRIMARY
        win._win.destroy()
    finally:
        p.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3.13.exe -m pytest tests/test_ui.py -v -k target_monitor`
Expected: FAIL — `ResultWindow` has no `_target_monitor`; `__init__` rejects `use_primary`.

- [ ] **Step 3: Implement**

In `phonexi/ui.py`, change `__init__` signature (line 22):

```python
    def __init__(self, root: tk.Tk, use_primary: bool = False) -> None:
        self._root = root
        self._use_primary = use_primary
```

Change the monitor call site (was line 52):

```python
        self._win.update_idletasks()
        mon = self._target_monitor()
```

Replace `_secondary_monitor` (lines 88-94) with:

```python
    def _target_monitor(self) -> dict:
        with mss.MSS() as sct:
            monitors = sct.monitors[1:]  # skip virtual combined (index 0)
            if self._use_primary:
                for mon in monitors:
                    if mon.get("is_primary", False):
                        return mon
                return monitors[0]
            for mon in monitors:
                if not mon.get("is_primary", False):
                    return mon
            return monitors[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3.13.exe -m pytest tests/test_ui.py -v`
Expected: PASS (new tests + existing ones).

- [ ] **Step 5: Commit**

```bash
git add phonexi/ui.py tests/test_ui.py
git commit -m "feat: ResultWindow target monitor selectable via use_primary"
```

---

### Task 2: `HotkeyListener` forwards `use_primary`

**Files:**
- Modify: `phonexi/listener.py:15` (`__init__`), `phonexi/listener.py:77` (`_start_capture`), `phonexi/listener.py:110` (`_open_recording_popup`)
- Test: `tests/test_listener.py`

- [ ] **Step 1: Write the failing test and fix the existing assertion**

In `tests/test_listener.py`, change the existing assertion (line 32) from:

```python
        mock_window_cls.assert_called_once_with(root)
```

to:

```python
        mock_window_cls.assert_called_once_with(root, use_primary=False)
```

Then add:

```python
def test_start_capture_forwards_use_primary(root):
    listener = HotkeyListener(tk_root=root, use_primary=True)

    with patch("phonexi.listener.capture", return_value=MagicMock()), \
         patch("phonexi.listener.ResultWindow") as mock_window_cls, \
         patch.object(listener, "_stream_image"):

        mock_window_cls.return_value = MagicMock()
        listener._start_capture()

        mock_window_cls.assert_called_once_with(root, use_primary=True)


def test_open_recording_popup_forwards_use_primary(root):
    listener = HotkeyListener(tk_root=root, use_primary=True)

    with patch("phonexi.listener.ResultWindow") as mock_window_cls:
        mock_window_cls.return_value = MagicMock()
        listener._open_recording_popup()

        mock_window_cls.assert_called_once_with(root, use_primary=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3.13.exe -m pytest tests/test_listener.py -v -k use_primary`
Expected: FAIL — `HotkeyListener.__init__` rejects `use_primary`; `ResultWindow` called without it.

- [ ] **Step 3: Implement**

In `phonexi/listener.py`, change `__init__` (line 15):

```python
    def __init__(self, tk_root, use_primary: bool = False) -> None:
        self._tk_root = tk_root
        self._use_primary = use_primary
```

In `_start_capture` (line 77), change:

```python
        win = ResultWindow(self._tk_root, use_primary=self._use_primary)
```

In `_open_recording_popup` (line 110), change:

```python
        win = ResultWindow(self._tk_root, use_primary=self._use_primary)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3.13.exe -m pytest tests/test_listener.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add phonexi/listener.py tests/test_listener.py
git commit -m "feat: HotkeyListener forwards use_primary to ResultWindow"
```

---

### Task 3: `main.py` CLI flag

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Implement argparse**

Replace `main.py` contents with:

```python
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
```

- [ ] **Step 2: Verify the flag parses**

Run: `python3.13.exe main.py --help`
Expected: help text shows `-P, --primary` option, exit code 0.

- [ ] **Step 3: Run the full suite**

Run: `python3.13.exe -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: -P/--primary flag selects popup monitor"
```

---

### Task 4: Docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the flag**

In `README.md`, under the `### 4. Run` section (around line 50-54), add after the existing `python main.py` block:

```markdown
Show the popup on the **primary** monitor instead of the secondary:

\`\`\`bash
python main.py -P
\`\`\`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document -P/--primary flag"
```

---

## Self-Review Notes

- **Spec coverage:** `-P`/default behavior → Task 3 + Task 1. Monitor selection logic → Task 1. Forwarding → Task 2. Tests (primary/secondary/fallback/CLI) → Tasks 1-3. README → Task 4.
- **Type consistency:** `use_primary: bool` used identically across `ResultWindow`, `HotkeyListener`, and `args.primary`. Method named `_target_monitor` everywhere.
- **No placeholders:** all steps contain concrete code/commands.
