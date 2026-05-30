# Processing Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OCR-free screenshot-to-answer pipeline using Ollama vision model with real-time streaming to a terminal-style Tkinter popup.

**Architecture:** Hotkey fires → `capture()` saves PNG → `process()` base64-encodes and streams from Ollama `/api/generate` → tokens arrive into `ResultWindow` (Tkinter `Toplevel`) via `root.after()` for thread safety. Main thread runs `tk.mainloop()`; pynput listener runs in daemon thread.

**Tech Stack:** `pynput`, `mss`, `requests`, `tkinter` (stdlib), Ollama local API (`llama3.2-vision:11b`)

> **Threading note:** The spec marked `main.py` as unchanged, but pynput's `.join()` blocks the main thread. Tkinter requires `mainloop()` on the main thread. This plan correctly restructures `main.py`: pynput listener → daemon thread, Tkinter mainloop → main thread.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `tests/__init__.py` | Create | Makes tests a package |
| `tests/test_config.py` | Create | Verify config constants |
| `tests/test_processor.py` | Create | Test process() with mocked HTTP |
| `tests/test_ui.py` | Create | Test ResultWindow interface |
| `tests/test_listener.py` | Create | Test _process_and_show integration |
| `phonexi/config.py` | Create | Central constants |
| `phonexi/processor.py` | Create | Path → Iterator[str], custom exceptions |
| `phonexi/ui.py` | Create | ResultWindow (Toplevel, streaming, dark theme) |
| `phonexi/listener.py` | Modify | Replace _capture_and_log with _process_and_show, accept tk_root |
| `main.py` | Modify | Hidden tk.Tk root, pynput in daemon thread, mainloop in main thread |
| `requirements.txt` | Modify | Add requests>=2.32, pytest>=8 |

---

## Task 1: Test infrastructure + `phonexi/config.py`

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `phonexi/config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from phonexi import config


def test_ollama_url():
    assert config.OLLAMA_URL == "http://localhost:11434"


def test_ollama_model():
    assert config.OLLAMA_MODEL == "llama3.2-vision:11b"


def test_timeout():
    assert isinstance(config.TIMEOUT_S, int)
    assert config.TIMEOUT_S > 0


def test_prompt_is_string():
    assert isinstance(config.PROMPT, str)
    assert len(config.PROMPT) > 0
```

- [ ] **Step 2: Create empty `tests/__init__.py` and run test to verify it fails**

```bash
# create tests/__init__.py (empty file)
```

Run:
```bash
pytest tests/test_config.py -v
```
Expected: `FAILED` — `ModuleNotFoundError: No module named 'phonexi.config'`

- [ ] **Step 3: Implement `phonexi/config.py`**

```python
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2-vision:11b"
TIMEOUT_S = 30
PROMPT = (
    "Extract the code from this screenshot. "
    "Identify the problem or question. "
    "Provide a concise solution."
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest tests/test_config.py -v
```
Expected:
```
PASSED tests/test_config.py::test_ollama_url
PASSED tests/test_config.py::test_ollama_model
PASSED tests/test_config.py::test_timeout
PASSED tests/test_config.py::test_prompt_is_string
```

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_config.py phonexi/config.py
git commit -m "feat: add config module with Ollama constants"
```

---

## Task 2: `phonexi/processor.py`

**Files:**
- Create: `tests/test_processor.py`
- Create: `phonexi/processor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_processor.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from phonexi.processor import ModelNotFoundError, OllamaNotRunningError, process


def _png(tmp_path: Path) -> Path:
    p = tmp_path / "shot.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    return p


def test_process_raises_when_ollama_not_running(tmp_path):
    img = _png(tmp_path)
    with patch("phonexi.processor.requests.post", side_effect=requests.exceptions.ConnectionError()):
        with pytest.raises(OllamaNotRunningError):
            list(process(img))


def test_process_raises_model_not_found(tmp_path):
    img = _png(tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.iter_lines.return_value = []
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        with pytest.raises(ModelNotFoundError):
            list(process(img))


def test_process_yields_tokens(tmp_path):
    img = _png(tmp_path)
    lines = [
        json.dumps({"response": "Hello", "done": False}).encode(),
        json.dumps({"response": " world", "done": False}).encode(),
        json.dumps({"response": "", "done": True}).encode(),
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = lines
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        tokens = list(process(img))
    assert tokens == ["Hello", " world"]


def test_process_stops_at_done_true(tmp_path):
    img = _png(tmp_path)
    lines = [
        json.dumps({"response": "A", "done": True}).encode(),
        json.dumps({"response": "B", "done": False}).encode(),
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = lines
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        tokens = list(process(img))
    assert tokens == ["A"]


def test_process_yields_timeout_sentinel_on_read_timeout(tmp_path):
    img = _png(tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    def _slow_lines():
        yield json.dumps({"response": "partial", "done": False}).encode()
        raise requests.exceptions.Timeout()

    mock_resp.iter_lines.return_value = _slow_lines()
    with patch("phonexi.processor.requests.post", return_value=mock_resp):
        tokens = list(process(img))
    assert "partial" in tokens
    assert tokens[-1] == "\n[timeout]"


def test_process_encodes_image_as_base64(tmp_path):
    import base64
    img = _png(tmp_path)
    raw = img.read_bytes()
    expected_b64 = base64.b64encode(raw).decode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        json.dumps({"response": "ok", "done": True}).encode()
    ]
    with patch("phonexi.processor.requests.post", return_value=mock_resp) as mock_post:
        list(process(img))
    payload = mock_post.call_args.kwargs["json"]
    assert payload["images"] == [expected_b64]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/test_processor.py -v
```
Expected: `FAILED` — `ModuleNotFoundError: No module named 'phonexi.processor'`

- [ ] **Step 3: Implement `phonexi/processor.py`**

```python
import base64
import json
from pathlib import Path
from typing import Iterator

import requests

from phonexi.config import OLLAMA_MODEL, OLLAMA_URL, PROMPT, TIMEOUT_S


class OllamaNotRunningError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


def process(path: Path) -> Iterator[str]:
    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": PROMPT,
        "images": [image_b64],
        "stream": True,
    }
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            stream=True,
            timeout=TIMEOUT_S,
        )
    except requests.exceptions.ConnectionError as exc:
        raise OllamaNotRunningError("Ollama is not running") from exc

    if response.status_code == 404:
        raise ModelNotFoundError(f"Model '{OLLAMA_MODEL}' not found")

    response.raise_for_status()

    try:
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("response", "")
            if token:
                yield token
            if chunk.get("done", False):
                break
    except requests.exceptions.Timeout:
        yield "\n[timeout]"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest tests/test_processor.py -v
```
Expected:
```
PASSED tests/test_processor.py::test_process_raises_when_ollama_not_running
PASSED tests/test_processor.py::test_process_raises_model_not_found
PASSED tests/test_processor.py::test_process_yields_tokens
PASSED tests/test_processor.py::test_process_stops_at_done_true
PASSED tests/test_processor.py::test_process_encodes_image_as_base64
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_processor.py phonexi/processor.py
git commit -m "feat: add processor module with Ollama streaming and error types"
```

---

## Task 3: `phonexi/ui.py`

**Files:**
- Create: `tests/test_ui.py`
- Create: `phonexi/ui.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ui.py
import tkinter as tk
import pytest
from phonexi.ui import ResultWindow


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_result_window_title(root):
    win = ResultWindow(root)
    assert win._win.title() == "Phonexi"
    win._win.destroy()


def test_result_window_is_topmost(root):
    win = ResultWindow(root)
    assert win._win.attributes("-topmost") == 1
    win._win.destroy()


def test_result_window_has_show_method(root):
    win = ResultWindow(root)
    assert callable(win.show)
    win._win.destroy()


def test_result_window_has_show_error_method(root):
    win = ResultWindow(root)
    assert callable(win.show_error)
    win._win.destroy()


def test_show_error_inserts_message(root):
    win = ResultWindow(root)
    win.show_error("test error message")
    content = win._text.get("1.0", tk.END)
    assert "test error message" in content
    win._win.destroy()


def test_insert_appends_text(root):
    win = ResultWindow(root)
    win._insert("hello")
    win._insert(" world")
    content = win._text.get("1.0", tk.END)
    assert "hello world" in content
    win._win.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/test_ui.py -v
```
Expected: `FAILED` — `ModuleNotFoundError: No module named 'phonexi.ui'`

- [ ] **Step 3: Implement `phonexi/ui.py`**

```python
import threading
import tkinter as tk
import tkinter.font as tkfont
from typing import Iterator


class ResultWindow:
    _FONT_CANDIDATES = ("Cascadia Code", "Consolas", "Courier New")
    _BG = "#0d0d0d"
    _FG = "#e0e0e0"
    _ERR_FG = "#ff5555"
    _WIDTH = 700
    _HEIGHT = 480

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._win = tk.Toplevel(root)
        self._win.title("Phonexi")
        self._win.configure(bg=self._BG)
        self._win.attributes("-topmost", True)
        self._win.bind("<Escape>", lambda _: self._win.destroy())
        self._win.protocol("WM_DELETE_WINDOW", self._win.destroy)

        font = self._resolve_font()
        self._text = tk.Text(
            self._win,
            bg=self._BG,
            fg=self._FG,
            font=font,
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=12,
            pady=12,
            insertbackground=self._FG,
        )
        self._text.tag_configure("err", foreground=self._ERR_FG)
        self._text.pack(fill=tk.BOTH, expand=True)

        self._win.update_idletasks()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x = (sw - self._WIDTH) // 2
        y = (sh - self._HEIGHT) // 2
        self._win.geometry(f"{self._WIDTH}x{self._HEIGHT}+{x}+{y}")

    def _resolve_font(self) -> tuple:
        available = tkfont.families()
        for name in self._FONT_CANDIDATES:
            if name in available:
                return (name, 11)
        return ("Courier New", 11)

    def _insert(self, text: str, tag: str = "") -> None:
        self._text.configure(state=tk.NORMAL)
        if tag:
            self._text.insert(tk.END, text, tag)
        else:
            self._text.insert(tk.END, text)
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)

    def show(self, iterator: Iterator[str]) -> None:
        self._root.after(0, self._insert, "> Analyzing screenshot...\n\n")

        def _stream() -> None:
            try:
                for token in iterator:
                    self._root.after(0, self._insert, token)
            except Exception as exc:
                self._root.after(0, self._insert, f"\n[error: {exc}]")

        threading.Thread(target=_stream, daemon=True).start()

    def show_error(self, msg: str) -> None:
        self._insert(f"> {msg}", "err")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest tests/test_ui.py -v
```
Expected:
```
PASSED tests/test_ui.py::test_result_window_title
PASSED tests/test_ui.py::test_result_window_is_topmost
PASSED tests/test_ui.py::test_result_window_has_show_method
PASSED tests/test_ui.py::test_result_window_has_show_error_method
PASSED tests/test_ui.py::test_show_error_inserts_message
PASSED tests/test_ui.py::test_insert_appends_text
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui.py phonexi/ui.py
git commit -m "feat: add ResultWindow terminal-style streaming popup"
```

---

## Task 4: Modify `phonexi/listener.py` + `main.py`

**Files:**
- Create: `tests/test_listener.py`
- Modify: `phonexi/listener.py`
- Modify: `main.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_listener.py
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest
from phonexi.listener import HotkeyListener


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_hotkey_listener_accepts_tk_root(root):
    listener = HotkeyListener(tk_root=root)
    assert listener._tk_root is root


def test_process_and_show_calls_capture_and_process(root):
    listener = HotkeyListener(tk_root=root)
    fake_path = MagicMock()
    fake_tokens = iter(["hello"])

    with patch("phonexi.listener.capture", return_value=fake_path) as mock_capture, \
         patch("phonexi.listener.process", return_value=fake_tokens) as mock_process, \
         patch("phonexi.listener.ResultWindow") as mock_window_cls:

        mock_win = MagicMock()
        mock_window_cls.return_value = mock_win

        listener._process_and_show()

        mock_capture.assert_called_once()
        mock_process.assert_called_once_with(fake_path)
        mock_window_cls.assert_called_once_with(root)
        mock_win.show.assert_called_once_with(fake_tokens)


def test_process_and_show_handles_ollama_not_running(root):
    from phonexi.processor import OllamaNotRunningError
    listener = HotkeyListener(tk_root=root)

    with patch("phonexi.listener.capture", return_value=MagicMock()), \
         patch("phonexi.listener.process", side_effect=OllamaNotRunningError()), \
         patch("phonexi.listener.ResultWindow") as mock_window_cls:

        mock_win = MagicMock()
        mock_window_cls.return_value = mock_win

        listener._process_and_show()

        mock_win.show_error.assert_called_once_with(
            "Ollama not running — start with: ollama serve"
        )


def test_process_and_show_handles_model_not_found(root):
    from phonexi.processor import ModelNotFoundError
    listener = HotkeyListener(tk_root=root)

    with patch("phonexi.listener.capture", return_value=MagicMock()), \
         patch("phonexi.listener.process", side_effect=ModelNotFoundError()), \
         patch("phonexi.listener.ResultWindow") as mock_window_cls:

        mock_win = MagicMock()
        mock_window_cls.return_value = mock_win

        listener._process_and_show()

        mock_win.show_error.assert_called_once_with(
            "Model not found — run: ollama pull llama3.2-vision:11b"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/test_listener.py -v
```
Expected: `FAILED` — `TypeError: HotkeyListener.__init__() got an unexpected keyword argument 'tk_root'`

- [ ] **Step 3: Rewrite `phonexi/listener.py`**

```python
import threading
from pynput import keyboard

from phonexi.processor import ModelNotFoundError, OllamaNotRunningError, process
from phonexi.screenshot import capture
from phonexi.ui import ResultWindow


class HotkeyListener:
    _TRIGGER_KEY = keyboard.KeyCode.from_char("p")
    _MODIFIER_KEY = keyboard.Key.shift_r

    def __init__(self, tk_root) -> None:
        self._tk_root = tk_root
        self._pressed: set = set()
        self._lock = threading.Lock()
        self._current_window = None

    def _on_press(self, key) -> None:
        with self._lock:
            self._pressed.add(key)

        if (
            self._MODIFIER_KEY in self._pressed
            and self._TRIGGER_KEY in self._pressed
        ):
            self._on_hotkey()

    def _on_release(self, key) -> None:
        with self._lock:
            self._pressed.discard(key)

    def _on_hotkey(self) -> None:
        threading.Thread(target=self._process_and_show, daemon=True).start()

    def _process_and_show(self) -> None:
        # Close any existing window before opening a new one
        if self._current_window is not None:
            try:
                self._tk_root.after(0, self._current_window._win.destroy)
            except Exception:
                pass

        path = capture()
        win = ResultWindow(self._tk_root)
        self._current_window = win
        try:
            tokens = process(path)
            win.show(tokens)
        except OllamaNotRunningError:
            win.show_error("Ollama not running — start with: ollama serve")
        except ModelNotFoundError:
            win.show_error("Model not found — run: ollama pull llama3.2-vision:11b")

    def start(self) -> None:
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
```

- [ ] **Step 4: Rewrite `main.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
pytest tests/test_listener.py -v
```
Expected:
```
PASSED tests/test_listener.py::test_hotkey_listener_accepts_tk_root
PASSED tests/test_listener.py::test_process_and_show_calls_capture_and_process
PASSED tests/test_listener.py::test_process_and_show_handles_ollama_not_running
PASSED tests/test_listener.py::test_process_and_show_handles_model_not_found
```

- [ ] **Step 6: Run full test suite**

Run:
```bash
pytest tests/ -v
```
Expected: All tests PASS, no failures.

- [ ] **Step 7: Commit**

```bash
git add tests/test_listener.py phonexi/listener.py main.py
git commit -m "feat: wire processor and UI into hotkey listener, fix threading model"
```

---

## Task 5: `requirements.txt` + install + smoke test

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update `requirements.txt`**

```
mss>=9.0.1
pynput>=1.7.7
requests>=2.32
pytest>=8.0
```

- [ ] **Step 2: Install dependencies**

Run:
```bash
pip install -r requirements.txt
```
Expected: All packages install without errors.

- [ ] **Step 3: Pull Ollama model (one-time setup)**

```powershell
ollama pull llama3.2-vision:11b
```
Expected: Model downloads (~7 GB). If Ollama not installed: https://ollama.com/download/windows

AMD GPU note — if responses are slow or GPU not used:
```powershell
$env:HSA_OVERRIDE_GFX_VERSION = "10.3.0"
ollama serve
```

- [ ] **Step 4: Manual smoke test**

```bash
python main.py
```

Expected console output:
```
[Phonexi] Running. Press Right Shift + P to capture. Ctrl+C to quit.
```

1. Press `Right Shift + P`
2. `screenshots/capture_<timestamp>.png` created
3. Phonexi popup appears centered, dark background
4. Text streams in: `> Analyzing screenshot...` then model response
5. Press `Escape` → window closes
6. Daemon keeps running, ready for next capture

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: add requests and pytest to requirements"
```
