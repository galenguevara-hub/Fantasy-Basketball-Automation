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

# Start the app
echo "Starting Fantasy Basketball app at http://localhost:8080"
echo "Press Ctrl+C to stop"
echo ""
PYTHONPATH=src python src/fba/app.py
