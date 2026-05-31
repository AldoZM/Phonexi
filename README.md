# Phonexi

Background daemon for Windows that captures a screenshot on hotkey and analyzes it with an AI vision model, streaming the response into a discreet dark popup.

## Demo

**Hotkey:** `Right Shift + P`

1. Screenshot captured from the monitor where your cursor is
2. Sent to Groq vision LLM (`llama-4-scout-17b`)
3. Response streamed into a dark terminal popup on your secondary monitor
4. Popup has syntax highlighting, Markdown formatting, and no taskbar entry

## Features

- Global hotkey detection via `pynput` (works in any app)
- Per-monitor screenshot — captures only the monitor where the cursor is
- Groq API free tier — 14,400 requests/day, no credit card required
- Syntax highlighting (Dracula theme) for code blocks in the response
- Markdown formatting: headings, bold, italic, inline code
- Popup appears on secondary/tertiary monitor — discreet
- No taskbar entry, no title bar — closes with `Escape`
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

Press `Right Shift + P` to capture and analyze. Press `Escape` to close the popup.

## Project Structure

```
Phonexi/
├── main.py               # Entry point
├── phonexi/
│   ├── config.py         # Env config (API key, model, prompt)
│   ├── screenshot.py     # Per-monitor screenshot capture
│   ├── processor.py      # Groq API call + token streaming
│   ├── listener.py       # Hotkey detection + orchestration
│   └── ui.py             # Dark popup with syntax highlighting
├── tests/                # pytest suite (17 tests)
├── requirements.txt
├── .env                  # NOT committed — add your key here
└── context.txt           # Full project context for AI assistants
```

## Requirements

- Windows 10/11
- Python 3.10+
- 3 monitors recommended (popup appears on secondary monitor)

## Tests

```bash
python -m pytest tests/ -v
```
