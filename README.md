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
- **Interview-style responses** — direct, confident, no filler
- **Responds in the question's language** — Spanish question → Spanish answer
- Groq API free tier — 14,400 requests/day, no credit card required
- Syntax highlighting (Dracula theme) for code blocks
- Markdown formatting: headings, bold, italic, inline code
- Popup on secondary monitor — discreet, no taskbar entry, no title bar
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

### 4. Run

```bash
python main.py
```

Show the popup on the **primary** monitor instead of the secondary:

```bash
python main.py -P
```

## Project Structure

```
Phonexi/
├── main.py               # Entry point
├── phonexi/
│   ├── config.py         # Env config (API key, model, prompt)
│   ├── screenshot.py     # Per-monitor screenshot capture
│   ├── processor.py      # Groq vision + text LLM streaming
│   ├── audio.py          # WASAPI loopback capture + Whisper transcription
│   ├── listener.py       # Hotkey detection + orchestration (two hotkeys)
│   └── ui.py             # Dark draggable popup with syntax highlighting
├── tests/                # pytest suite (17 tests)
├── requirements.txt
├── .env                  # NOT committed — add your key here
└── context.txt           # Full project context for AI assistants
```

## Requirements

- Windows 10/11
- Python 3.10+
- 2+ monitors recommended (popup appears on secondary monitor)

## Tests

```bash
python -m pytest tests/ -v
```
