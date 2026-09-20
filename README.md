# Phonexi

Discreet background daemon for Windows that captures screenshots or listens to system audio and answers with an AI model — designed for technical interviews.

## Hotkeys

| Hotkey | Action |
|--------|--------|
| `Right Shift + P` | Screenshot → Groq vision LLM → response |
| `Right Alt + P` (1st press) | Start listening to system audio |
| `Right Alt + P` (2nd press) | Stop → Whisper transcribes → LLM responds |
| `Escape` | Close popup |

## Features

- **Screenshot mode** — captures only the monitor where your cursor is
- **Audio mode** — captures system audio via WASAPI loopback (hears the interviewer on a call, not your mic)
- **Web mode (`-w`)** — serves answers to your phone over the LAN (scan a terminal QR), auto-updating via SSE; nothing shows on a shared screen
- **Region capture (`-r`)** — grabs a 16:9 box around the cursor instead of the whole monitor, so the model reads the problem and not the rest of your desktop
- **Prior context (`-c`)** — point it at a `.md` or `.txt` file (the job posting, the stack, your own experience) and the model answers oriented to it instead of cold
- **Interview-style responses** — direct, confident, no filler
- **Responds in the question's language** — Spanish question → Spanish answer
- Groq API free tier — 14,400 requests/day, no credit card required
- Syntax highlighting (Dracula theme) for code blocks
- Markdown formatting: headings, bold, italic, inline code
- Popup on secondary monitor by default — discreet, no taskbar entry, no title bar (use `-P`/`--primary` to show it on the primary monitor)
- Draggable window — click and drag to reposition
- Replaces previous popup on repeated hotkey press

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a free Groq API key

1. Go to [console.groq.com](https://console.groq.com)
2. Create account (free, no credit card)
3. API Keys → Create API key
4. Copy the key (`gsk_...`)

### 3. Configure

Create a `.env` file in the project root:

```
GROQ_API_KEY=gsk_your_key_here
```

Optional keys, all with sensible defaults:

- `GROQ_MODEL_VISION` — model used for screenshot mode
- `GROQ_MODEL_TEXT` — model used for audio and text mode
- `GROQ_MAX_TOKENS` — cap on the answer length, default `900`
- `GROQ_REASONING_VISION` / `GROQ_REASONING_TEXT` — thinking budget, default `none` and `low`

Keep `GROQ_MAX_TOKENS` below your account's output-tokens-per-minute allowance, which is 1000 on the free tier. Groq compares the cap against that limit by itself and refuses the whole request with a 429 before generating anything, so 1024 fails while 900 works. A fresh minute lets the larger value through, which makes the failure look intermittent when it is not.

**Gemini (optional).** Add `GEMINI_API_KEY` from [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — the free tier needs no card. Whichever key is written **highest** in `.env` picks the default provider; move a line up to switch. Gemini keys: `GEMINI_MODEL` (default `gemini-3.8-flash`, used for text and captures), `GEMINI_MAX_TOKENS` (default `2048`), `GEMINI_REASONING` (`low`, `medium` or `high`; `gemini-3.8-flash` refuses `minimal`). Audio is still transcribed by Groq Whisper, so audio mode needs `GROQ_API_KEY` either way. On the free tier Google may use prompts and captures to improve its products.

The thinking budget matters more than it looks. Left at the model default, a reasoning model spends most of its output allowance narrating to itself before it answers, and on the free tier that allowance is the first thing to run out. The accepted values differ by model family: qwen takes `none` or `default`, gpt-oss takes `low`, `medium` or `high`. A value the model rejects is dropped automatically.

### 4. Run

```bash
python main.py
python main.py -help     # every flag, examples and .env settings
```

Pick the model by hand before starting — only providers with a key are listed:

```bash
python main.py -model
```

```
Choose a model (Up/Down, Enter to confirm, Esc to cancel):
> gemini  gemini-3.8-flash        text, vision, audio
  gemini  gemini-3.1-flash-lite   text, vision, audio
  groq    openai/gpt-oss-120b     text
  groq    qwen/qwen3.8-27b        text, vision
```

Gemini's free tier answers 503 when a model is busy. Phonexi then retries once on another Gemini model (3.8-flash first) and the popup opens with a line saying which one answered; only if that one is busy too does the popup show the error. A model that reads images answers both hotkeys; a text-only one answers audio and leaves captures on the `.env` vision model. `-model` needs a console, so it does not work from `start_phonexi.vbs`.

Answer with a local CLI instead of the API, using a subscription already paid for:

```bash
python main.py -cli
```

```
Choose a CLI (Up/Down, Enter to confirm, Esc to cancel):
> cli     claude  text, vision
  cli     agy     text, vision
```

Only CLIs found on `PATH` are listed, and a missing one stops startup rather than
surfacing mid-interview. Everything else is unchanged: same hotkeys, same capture,
same popup, same web mode. What changes is who answers.

Two things to know before relying on it:

- **It is slower.** Every question launches a process, so the first word takes
  3 to 7 seconds against Groq's near-instant reply. Measured on 2026-09-20:
  `claude` answers a capture in about 10 s (first text at ~5 s), `agy` in about
  9 s (first text at ~7 s). A long answer from `claude` can reach 20 s.
- **Audio still needs `GROQ_API_KEY`.** Neither CLI transcribes a `.wav`, so
  Whisper keeps doing that half of the voice flow. Only the answer comes from
  the CLI.

These are coding agents, not chat endpoints, so both are kept on a short leash:
`claude` runs with `--allowed-tools Read` in capture mode and no tools at all in
voice mode. `agy` has **no flag to restrict tools**, only `--sandbox`, which is a
weaker guarantee — worth knowing before picking it for a live interview.

Like `-model`, `-cli` needs a console, so it does not work from `start_phonexi.vbs`.

Capture a box around the cursor instead of the whole monitor:

```bash
python main.py -r            # 1280x720 around the cursor
python main.py -r 960x540    # a tighter box
```

Keep the box 16:9. Groq prices an image by its aspect ratio rather than its pixel count, so 1280x720 and 640x360 both cost 783 input tokens while a 4:3 box of the same content costs 1807. Near a screen edge the box slides inward instead of shrinking, which keeps that ratio constant. A box larger than the monitor falls back to the full monitor.

Region mode is about accuracy, not cost: a full monitor and a region cost the same. What it buys is a model that is not reading your taskbar.

Old captures are pruned at startup, keeping the newest 20.

Show the popup on the **primary** monitor instead of the secondary:

```bash
python main.py -P
```

Serve responses to your **phone** instead of an on-screen popup (useful when
screen-sharing or on a single monitor):

```bash
python main.py -w
```

Load a **prior-context** file so answers come out oriented:

```bash
python main.py -c contexto.md
```

The file is read and validated **before** the hotkeys are registered, so the context
is already loaded when you press the first one. Only `.md` and `.txt` are accepted,
up to 20,000 characters. If the path does not exist, has another extension, is not
UTF-8 text, is empty, or is too large, Phonexi prints the reason and exits without
starting — you find out on launch, not mid-interview. The flag is optional and
combines with `-P` and `-w`.

Only the sections that answer the question are sent, not the whole file. Groq's
free tier allows 8,000 tokens per minute and a full ficha costs about 4,200 of
them, so sending it whole capped you at one question per minute; picking sections
brings a question down to 1,000-1,800 tokens. The rules block above the first
numbered section always travels with them. See `phonexi/relevance.py`.

Keep those files in `contexts/` — see [`contexts/README.md`](contexts/README.md)
for what to put in one and why the files themselves are never committed.

Put in it whatever orients the answer: the job posting, the stack, the seniority, the
language of the interview, your own background. It reaches the model as background
information, never as the question to answer.

Phonexi prints a QR code and the LAN URL in the terminal. Scan the QR with your
phone (same WiFi) — responses appear in the browser, auto-updating via SSE.
No popup is shown on the shared screen. The hotkeys are unchanged.
**Note:** the server has no authentication; use it on a personal hotspot or a
trusted network, not on corporate or monitored WiFi.

## Project Structure

```
Phonexi/
├── main.py               # Entry point
├── contexts/             # Your -c context files (git-ignored; see its README)
├── phonexi/
│   ├── briefing.py       # Optional -c prior-context file: load + validate
│   ├── relevance.py      # Picks the ficha sections each question needs
│   ├── config.py         # Env config (API key, model, prompt)
│   ├── screenshot.py     # Per-monitor screenshot capture
│   ├── processor.py      # Vision + text LLM streaming (Groq or Gemini)
│   ├── providers.py      # Model catalog, key order, active selection
│   ├── picker.py         # Arrow-key picker, shared by -model and -cli
│   ├── engines/          # Who answers: the API, or a local CLI (-cli)
│   │   ├── base.py       # Engine protocol + shared subprocess/NDJSON machinery
│   │   ├── api.py        # Adapts processor.py (Groq/Gemini) to the interface
│   │   ├── claude.py     # Claude Code: flags and stream_event parser
│   │   └── agy.py        # Antigravity: flags and step_update parser
│   ├── audio.py          # WASAPI loopback capture + Whisper transcription
│   ├── listener.py       # Hotkey detection + orchestration (view-agnostic via view_factory)
│   ├── ui.py             # Dark draggable popup with syntax highlighting
│   └── webserver.py      # Web mode: local HTTP + SSE, QR, phone-readable page
├── tests/                # pytest suite (270 tests)
├── requirements.txt
├── .env                  # NOT committed — add your key here
└── context.txt           # Full project context for AI assistants
```

## Requirements

- Windows 10/11
- Python 3.10+
- 2+ monitors recommended for popup mode (or use `-w` web mode with a phone on the same WiFi — no second monitor needed)

## Tests

```bash
python -m pytest tests/ -v
```
