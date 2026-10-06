# Stealth Popup (Anti-Screen Share) Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide the result popup window (`ResultWindow`) from screen sharing (Google Meet, Microsoft Teams, Zoom, Discord, OBS) using Windows `SetWindowDisplayAffinity` (`WDA_EXCLUDEFROMCAPTURE`), while keeping it visible on the local monitor.

**Architecture:** 
- Config variable `STEALTH_MODE` in `phonexi/config.py` defaults to `True`.
- Helper `set_window_stealth` in `phonexi/ui.py` applies `SetWindowDisplayAffinity(top_hwnd, 0x11)` on the root `HWND` obtained via `GetAncestor(hwnd, GA_ROOT)`.
- `ResultWindow` sets display affinity upon creation if `stealth` is enabled.
- `main.py` provides `--no-stealth` argument for debugging/recording.

**Tech Stack:** Python 3.12/3.13, Tkinter, Win32 API (`ctypes`), pytest.

---

## File Structure

- `docs/superpowers/specs/2026-10-05-stealth-popup-design.md` — Design specification.
- `phonexi/config.py` — Add `STEALTH_MODE`.
- `phonexi/ui.py` — Add `set_window_stealth` and `ResultWindow` stealth parameter.
- `main.py` — Add `--no-stealth` argument and wire to popup view factory.
- `tests/test_ui.py` — Add unit tests for stealth activation and fallback.
- `tests/test_config.py` — Add test for `STEALTH_MODE`.
- `README.md` — Document stealth mode and CLI flag.

---

### Task 1: Configuration in `phonexi/config.py`

**Files:**
- Modify: `phonexi/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write test for `STEALTH_MODE`**
  Add test asserting `config.STEALTH_MODE` is a boolean and defaults to `True`.
- [ ] **Step 2: Add `STEALTH_MODE` in `phonexi/config.py`**
  ```python
  STEALTH_MODE: bool = os.getenv("STEALTH_MODE", "1") != "0"
  ```
- [ ] **Step 3: Run pytest on `tests/test_config.py`**

---

### Task 2: Stealth Window Helper & `ResultWindow` Integration

**Files:**
- Modify: `phonexi/ui.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Write tests in `tests/test_ui.py`**
  - Test `set_window_stealth` calls `SetWindowDisplayAffinity` with `0x11`.
  - Test fallback to `0x01` if `0x11` returns 0.
  - Test non-Windows safety.
  - Test `ResultWindow(root, stealth=False)` skips affinity.
- [ ] **Step 2: Implement `set_window_stealth` in `phonexi/ui.py`**
  Extract root HWND via `GetAncestor(hwnd, 2)` and set display affinity.
- [ ] **Step 3: Update `ResultWindow.__init__`**
  Accept `stealth: bool | None = None` (defaulting to `STEALTH_MODE`), and call `set_window_stealth` on `self._win`.
- [ ] **Step 4: Run pytest on `tests/test_ui.py`**

---

### Task 3: CLI Flag in `main.py`

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Add `--no-stealth` flag to parser**
  Add argument to `_parse_args()` in `main.py`.
- [ ] **Step 2: Forward stealth option in `_run_popup`**
  Pass custom `view_factory` when `stealth=False` or pass `stealth` flag.
- [ ] **Step 3: Add CLI tests in `tests/test_main.py`**
  Verify `--no-stealth` parses as expected and defaults to `False`.
- [ ] **Step 4: Run pytest on `tests/test_main.py`**

---

### Task 4: Documentation & Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README.md with feature details**
- [ ] **Step 2: Run full test suite (`pytest`)**
- [ ] **Step 3: Smoke test live popup script with screen capture simulation**
