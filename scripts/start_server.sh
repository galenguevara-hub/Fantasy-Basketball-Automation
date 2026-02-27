#!/bin/bash
# Start the Fantasy Basketball standings web app

# Change to project root (this script lives in scripts/, so go up one level)
cd "$(dirname "$0")/.."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found."
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && playwright install chromium"
    exit 1
fi

# Activate venv
source venv/bin/activate

# Warn if no saved Yahoo session exists
if [ ! -f "data/browser_state.json" ]; then
    echo "No Yahoo session found (data/browser_state.json missing)."
    echo "Run this first: PYTHONPATH=src python src/fba/scraper.py --login"
    echo ""
fi

RAW_UI_MODE="${FBA_UI_MODE:-react}"
if [ "${RAW_UI_MODE}" = "legacy" ]; then
    UI_MODE="legacy"
    echo "UI mode: legacy"
elif [ "${RAW_UI_MODE}" = "auto" ]; then
    UI_MODE="react"
    echo "UI mode: auto (compatibility alias; treated as react)"
elif [ "${RAW_UI_MODE}" = "react" ]; then
    UI_MODE="react"
    echo "UI mode: react (default)"
else
    UI_MODE="react"
    echo "UI mode: ${RAW_UI_MODE} (invalid; treated as react)"
fi

if [ "${UI_MODE}" = "react" ] && [ ! -f "frontend/dist/index.html" ]; then
    echo "Error: React UI mode requires frontend/dist/index.html, but it is missing."
    echo "Run: npm --prefix frontend run build"
    echo "Or force legacy templates: FBA_UI_MODE=legacy ./scripts/start_server.sh"
    exit 1
elif [ "${UI_MODE}" = "legacy" ]; then
    echo "Legacy templates forced via FBA_UI_MODE=legacy."
fi
echo ""

# Start the app
echo "Starting Fantasy Basketball app at http://localhost:8080"
echo "Press Ctrl+C to stop"
echo ""
PYTHONPATH=src python src/fba/app.py
