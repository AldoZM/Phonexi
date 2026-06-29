# Web Status Animation — Design

**Date:** 2026-06-28
**Scope:** Web output mode (`-w` / `--web`) only.

## Problem

In web mode the phone page shows a single static status line ("Waiting for
Phonexi..."). There is no visual signal that the server is alive and working.
A user looking at the page can't tell whether Phonexi is running or frozen.

## Goal

Animate the status legend with cycling dots (1 → 2 → 3 → 1) so the page always
shows a "breathing" indicator that the server is up. Two waiting legends frame
the request lifecycle:

- Before a question is asked: `Waiting for a question`
- After a response is printed: `Waiting for the next question`

Intermediate server statuses (Listening / Analyzing / the transcribed question)
also animate.

## Constraints / Decisions

- **Language: English.** No translation. Server status strings stay as they are
  in `listener.py` ("🎙 Listening...", "⏳ Analyzing...", "❓ <question>").
- **No changes to `listener.py`.** Shared status strings feed both the Tkinter
  popup (`ResultWindow`) and the web view (`WebView`); leaving them untouched
  keeps the popup behavior unchanged and avoids a fragile translation layer.
- **Animation runs client-side** (JavaScript in `INDEX_HTML`), not server-pushed
  frames. No extra SSE traffic; smooth; no server thread load.
- **Single file touched:** `phonexi/webserver.py` (the `INDEX_HTML` string and
  its embedded JS). Tests in `tests/test_webserver.py`.

## State table

| Moment | Base text | Animates |
|---|---|---|
| Page load / waiting for question | `Waiting for a question` | yes |
| Recording audio | `🎙 Listening` (dots stripped) | yes |
| Processing | `⏳ Analyzing` (dots stripped) | yes |
| Question transcribed | `❓ <question>` | yes |
| After response printed | `Waiting for the next question` | yes |
| Error | error text (red) | no |

## How double-dots are avoided without touching Python

Server status strings arrive with trailing static dots ("Listening...",
"Analyzing..."). The client strips trailing dots/whitespace from the base before
appending the animated dots: `"🎙 Listening..."` → base `"🎙 Listening"` →
rendered as `🎙 Listening.` / `🎙 Listening..` / `🎙 Listening...`. This keeps
the animation uniform across all states with zero Python changes.

## Client behavior (JS in `INDEX_HTML`)

```js
let base = "Waiting for a question";
let animate = true, dots = 1;
setInterval(() => {
  if (!animate) return;
  statusEl.textContent = base + ".".repeat(dots);
  dots = dots % 3 + 1;
}, 500);
```

SSE event handlers update `base` / `animate`:

- `status`  → `base = text.replace(/[.\s]+$/, '')`; `animate = true`; clear `.err` class
- `response`→ render markdown; then `base = "Waiting for the next question"`; `animate = true`
- `error`   → `animate = false`; set `.err` class; `textContent = text` (no dots)

The `#status` element uses a fixed minimum width (or the text is otherwise
stabilized) so the line does not shift horizontally as the dot count changes.

## Data flow

```
SSE event ──> JS handler sets {base, animate}
                                   │
        setInterval (500ms) ───────┘──> statusEl.textContent = base + dots
```

The 500ms timer is the only driver of the visible dot count. SSE events never
carry dot frames; they only change which base text is shown and whether it
animates.

## Testing

`tests/test_webserver.py` adds assertions against the `INDEX_HTML` string:

- Contains both waiting legends: `Waiting for a question` and
  `Waiting for the next question`.
- Contains the animation primitives: a `setInterval` call and `repeat(` for the
  dots.
- Contains the trailing-dot strip (`replace(` with the trailing-dot regex) so a
  server status like "Listening..." does not double its dots.

No server-side logic changes, so existing `WebServer` / `Broadcaster` / `WebView`
tests remain valid and untouched.

## Out of scope

- Translating any status string to Spanish.
- Adding an intermediate "Analyzing" status to screenshot mode (web screenshot
  flow emits no intermediate status today; during processing the page keeps
  animating the previous waiting legend, which still signals "working").
- Any change to the Tkinter popup (`ResultWindow`).
