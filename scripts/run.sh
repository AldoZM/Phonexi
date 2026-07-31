#!/usr/bin/env bash
# Launch Phonexi (Linux, web mode). Run AFTER a normal log out / log in
# (the 'input' group must be active in a real login session — not via newgrp,
# which breaks the ScreenCast portal).
set -euo pipefail

PROJECT="$HOME/Documents/Phonexi"
cd "$PROJECT"

# 1. input group active in this session?
if ! id -nG | tr ' ' '\n' | grep -qx input; then
    echo "ERROR: your 'input' group is not active in this session."
    if id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
        echo "You ARE in the group, but this session predates it."
        echo "-> Log OUT and back IN (a full session), then run this script again."
    else
        echo "-> Run: sudo usermod -aG input \"$USER\"   then log out/in."
    fi
    exit 1
fi

# 2. venv present?
if [ ! -x .venv/bin/python ]; then
    echo "ERROR: .venv missing. Create it:"
    echo "  python3 -m venv --system-site-packages .venv"
    echo "  .venv/bin/pip install -r requirements-linux.txt"
    exit 1
fi

# 3. Groq key present?
if [ ! -f .env ]; then
    echo "ERROR: .env missing. Add your key:  echo 'GROQ_API_KEY=gsk_...' > .env"
    exit 1
fi

echo "[run.sh] Starting Phonexi web mode. A ScreenCast consent dialog appears once."
echo "[run.sh] Right Shift + P = screenshot   Right Alt + P = audio   Ctrl+C = quit"
exec .venv/bin/python main.py -w
