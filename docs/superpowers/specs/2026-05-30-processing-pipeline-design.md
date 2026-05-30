# Phonexi — Processing Pipeline Design

**Date:** 2026-05-30  
**Status:** Approved  

## Goal

Extend Phonexi so that after capturing a screenshot (Right Shift + P), the image is sent to a local vision LLM, the response streams in real time, and a terminal-style popup window displays it immediately. Zero external APIs, zero internet required.

## Constraints

- Local only — Ollama running on `localhost:11434`
- Speed is the primary objective — first token visible within ~1-3 seconds
- Hardware: AMD Radeon RX 6600 (8 GB VRAM) + 32 GB RAM
- No new mandatory Python dependencies beyond `requests`
- MarkItDown explicitly excluded — adds latency without benefit for raw screenshots

## Architecture

Single-model, single-call, streaming pipeline:

```
Hotkey (pynput daemon thread)
  → screenshot.py: capture() → Path (~50ms)
  → processor.py: process(path) → Iterator[str]
      - encode PNG as base64
      - POST /api/generate to Ollama (stream=True)
      - yield tokens as they arrive
  → ui.py: ResultWindow.show(token_iterator)
      - open Tkinter window on first token
      - append tokens to Text widget in real time
      - Escape or ✕ closes window
```

## Model

**`llama3.2-vision:11b`** (Q4_K_M quantization)

- ~7 GB VRAM — fits RX 6600
- 32 GB RAM keeps model warm between calls (no reload overhead)
- Single model handles both image understanding and code reasoning
- No model swaps, no pipeline overhead

Rejected alternatives:
- `llava:7b` — weaker code reasoning
- `moondream2` — too imprecise for code
- Two-model pipeline (`moondream2` + `qwen2.5-coder:7b`) — model swap adds 3-5s latency

## Modules

### New: `phonexi/config.py`
Central configuration. Single source of truth.

```python
OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2-vision:11b"
TIMEOUT_S    = 30
PROMPT       = (
    "Extract the code from this screenshot. "
    "Identify the problem or question. "
    "Provide a concise solution."
)
```

### New: `phonexi/processor.py`
Single responsibility: `Path → Iterator[str]`

- Read PNG file, encode as base64
- POST to `{OLLAMA_URL}/api/generate` with `stream=True`
- Parse NDJSON response, yield `response` field per chunk
- Define and raise `OllamaNotRunningError` (connection refused) and `ModelNotFoundError` (HTTP 404) — both defined in this module

### New: `phonexi/ui.py`
Single responsibility: render streaming tokens in a popup window

- `ResultWindow` class wraps a Tkinter `Toplevel`
- Dark terminal theme: background `#0d0d0d`, foreground `#e0e0e0`
- Monospace font: Cascadia Code → Consolas → Courier New (fallback chain)
- `show(iterator)`: opens window, consumes iterator, inserts tokens via `after()` (thread-safe)
- `show_error(msg)`: opens window immediately with static error text in red (`#ff5555`)
- `Escape` / window close destroys the window
- Always on top (`topmost=True`)
- No scroll buttons — mouse wheel scrolls the Text widget

### Modified: `phonexi/listener.py`
Replace `_capture_and_log` with `_process_and_show`:

```python
def _process_and_show(self) -> None:
    path = capture()
    try:
        tokens = process(path)
        ResultWindow().show(tokens)
    except OllamaNotRunningError:
        ResultWindow().show_error("Ollama not running — start with: ollama serve")
    except ModelNotFoundError:
        ResultWindow().show_error("Model not found — run: ollama pull llama3.2-vision:11b")
```

### Unchanged: `screenshot.py`, `main.py`, `phonexi/__init__.py`

## UI Spec

```
┌─ Phonexi ────────────────────────────┐
│                                      │
│ > Analyzing screenshot...            │
│                                      │
│   def bubble_sort(arr):              │
│       for i in range(n-1):  ← bug   │
│                                      │
│   Fix: range(n-1) → range(n)        │
│ ▌                                    │
└──────────────────────────────────────┘
```

- Window size: 700 × 480 px, centered on primary monitor
- No toolbar, no menu bar
- Title bar: `Phonexi` (OS-native)
- Escape closes; clicking outside does NOT close (avoid accidental dismiss)
- After stream ends, cursor stops blinking

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Ollama not running | `show_error("Ollama not running — start with: ollama serve")` |
| Model not pulled | `show_error("Model not found — run: ollama pull llama3.2-vision:11b")` |
| Stream timeout (>30s) | Truncate stream, append `"\n[timeout]"` to window |
| Screenshot fails | Print to console, no popup |
| Window already open | Close existing, open new (rapid successive hotkeys) |

No silent fallbacks. No automatic retries.

## Dependencies

```
# requirements.txt additions
requests>=2.32
```

Tkinter: Python stdlib — no install required.

## Setup (one-time)

```powershell
# 1. Install Ollama
#    https://ollama.com/download/windows

# 2. Pull model
ollama pull llama3.2-vision:11b

# 3. AMD GPU on Windows (if needed)
$env:HSA_OVERRIDE_GFX_VERSION = "10.3.0"
ollama serve

# 4. Install Python deps
pip install -r requirements.txt

# 5. Run
python main.py
```

## File Tree After Implementation

```
phonexi/
├── __init__.py       (unchanged)
├── config.py         (new)
├── listener.py       (modified — _process_and_show replaces _capture_and_log)
├── processor.py      (new)
├── screenshot.py     (unchanged)
└── ui.py             (new)
```
