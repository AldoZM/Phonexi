# Web Status Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Animate the web-mode status legend with cycling dots (1→2→3) and frame the request lifecycle with two waiting legends, so the phone page always signals the server is alive.

**Architecture:** Pure client-side change inside the `INDEX_HTML` string in `phonexi/webserver.py`. A `setInterval` timer appends cycling dots to a `base` text; SSE event handlers only change `base` and an `animate` flag. No server-push frames, no changes to `listener.py` or `WebView`/`WebServer` Python logic.

**Tech Stack:** Python 3.14 (stdlib `http.server`), vanilla JavaScript + SSE (`EventSource`) in the served HTML, pytest for tests.

## Global Constraints

- **Language: English.** No status string translated to Spanish.
- **Do not modify `phonexi/listener.py`.** Its status strings ("🎙 Listening...", "⏳ Analyzing...", "❓ <question>") feed both the Tkinter popup and the web view; leave them untouched.
- **Only `phonexi/webserver.py` (the `INDEX_HTML` string) and `tests/test_webserver.py` change.**
- **No backslash-escape regex inside `INDEX_HTML`.** Python 3.14 raises `SyntaxWarning` for invalid escape sequences (e.g. `\s`) in a normal (non-raw) string. Strip trailing dots/whitespace with `trimEnd()` + `endsWith('.')`, not a regex.
- Dot cycle: `1 → 2 → 3 → 1` every 500ms. Animation stops on `error`.
- Waiting legends, verbatim: `Waiting for a question` and `Waiting for the next question`.

---

### Task 1: Animated status legend in the web page

**Files:**
- Modify: `phonexi/webserver.py` (the `INDEX_HTML` constant: the `#status` default text and the `<script>` block)
- Test: `tests/test_webserver.py`

**Interfaces:**
- Consumes: existing SSE events published by `WebView` — `status {text}`, `error {text}`, `response {markdown}` (unchanged).
- Produces: no new Python symbols. The `INDEX_HTML` string gains the two legend literals and the animation JS; tests assert on its content.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_webserver.py` (the file already imports `INDEX_HTML`):

```python
def test_index_html_has_waiting_legends():
    assert "Waiting for a question" in INDEX_HTML
    assert "Waiting for the next question" in INDEX_HTML


def test_index_html_has_dot_animation():
    assert "setInterval(" in INDEX_HTML
    assert 'repeat(' in INDEX_HTML


def test_index_html_strips_trailing_dots_without_regex():
    # Trailing dots from server statuses ("Listening...") must be stripped so the
    # animated dots don't double up — done with trimEnd()+endsWith, no backslash regex.
    assert "trimEnd()" in INDEX_HTML
    assert "endsWith('.')" in INDEX_HTML
    assert "[.\\s]" not in INDEX_HTML  # no backslash-escape regex (Python 3.14 SyntaxWarning)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_webserver.py -k "legends or animation or strips" -v`
Expected: 3 FAILS — `assert 'Waiting for a question' in INDEX_HTML` etc. (strings not present yet).

- [ ] **Step 3: Update the `INDEX_HTML` `#status` default text**

In `phonexi/webserver.py`, change the status div default:

```html
<div id="status">Waiting for a question</div>
```

(was `<div id="status">Waiting for Phonexi...</div>`)

- [ ] **Step 4: Replace the `<script>` block in `INDEX_HTML`**

Replace the entire existing `<script> ... </script>` block (the one with `const statusEl ...`) with:

```html
<script>
  const statusEl = document.getElementById('status');
  const respEl = document.getElementById('response');

  let base = "Waiting for a question";
  let animate = true;
  let dots = 1;
  setInterval(() => {
    if (!animate) return;
    statusEl.textContent = base + ".".repeat(dots);
    dots = dots % 3 + 1;
  }, 500);

  const es = new EventSource('/events');
  es.addEventListener('status', e => {
    statusEl.className = '';
    let t = JSON.parse(e.data).text.trimEnd();
    while (t.endsWith('.')) t = t.slice(0, -1);
    base = t;
    animate = true;
  });
  es.addEventListener('error', e => {
    if (!e.data) return;
    animate = false;
    statusEl.className = 'err';
    statusEl.textContent = JSON.parse(e.data).text;
  });
  es.addEventListener('response', e => {
    respEl.innerHTML = marked.parse(JSON.parse(e.data).markdown);
    respEl.querySelectorAll('pre code').forEach(b => hljs.highlightElement(b));
    base = "Waiting for the next question";
    animate = true;
  });
</script>
```

Notes for the implementer:
- The status text is left-aligned in a full-width block (`#status` CSS unchanged), so appending dots at the end does not shift any visible character — no extra CSS needed.
- `trimEnd()` removes trailing whitespace including the `\n` that `listener.py` appends to the question string (`❓ {text}\n`); the `while` loop then removes trailing dots. No backslash regex.
- `EventSource('/events')`, `marked`, and `highlight` references are preserved, so existing tests (`test_index_html_references_eventsource_and_libs`, `test_webserver_picks_port_and_serves_index`) still pass.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `python -m pytest tests/test_webserver.py -k "legends or animation or strips" -v`
Expected: 3 PASS.

- [ ] **Step 6: Run the full suite to verify nothing regressed**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS (the 3 new ones plus the existing suite, including the unchanged `test_index_html_references_eventsource_and_libs` and `test_webserver_picks_port_and_serves_index`).

- [ ] **Step 7: Commit**

```bash
git add phonexi/webserver.py tests/test_webserver.py
git commit -m "feat: animated status legend with cycling dots in web mode"
```

---

## Self-Review

**1. Spec coverage:**
- Two waiting legends (idle / after response) → Task 1 Steps 3, 4 (`Waiting for a question`, `Waiting for the next question`). ✓
- Cycling dots 1→2→3 every 500ms → Step 4 `setInterval` + `repeat(dots)`. ✓
- Intermediate statuses animate, trailing dots stripped → Step 4 `status` handler (`trimEnd()` + `while endsWith('.')`). ✓
- Error stops animation, red → Step 4 `error` handler (`animate = false`, `className = 'err'`). ✓
- Client-side only, no `listener.py` change, single file → Global Constraints + Task 1 Files. ✓
- Layout does not jitter → Step 4 note (left-aligned block, no CSS needed). ✓
- Tests assert legends + animation primitives + trailing-dot strip → Step 1. ✓

**2. Placeholder scan:** No TBD/TODO; all code shown verbatim. ✓

**3. Type consistency:** No new Python symbols; JS variables (`base`, `animate`, `dots`, `statusEl`, `respEl`) consistent across the single script block. Test substrings (`"setInterval("`, `"repeat("`, `"trimEnd()"`, `"endsWith('.')"`) match the literals in Step 4. ✓
