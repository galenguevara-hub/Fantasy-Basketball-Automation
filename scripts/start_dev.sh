#!/bin/bash
# Start Flask API + React Vite dev server together.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d "venv" ]; then
  echo "Virtual environment not found."
  echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && playwright install chromium"
  exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "Frontend dependencies not installed."
  echo "Run: cd frontend && npm install"
  exit 1
fi

source venv/bin/activate

cleanup() {
  if [ -n "${FLASK_PID:-}" ] && kill -0 "$FLASK_PID" 2>/dev/null; then
    kill "$FLASK_PID" 2>/dev/null || true
  fi
  if [ -n "${VITE_PID:-}" ] && kill -0 "$VITE_PID" 2>/dev/null; then
    kill "$VITE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting backend on http://localhost:8080"
PYTHONPATH=src python src/fba/app.py &
FLASK_PID=$!

echo "Starting frontend on http://localhost:5173"
npm --prefix frontend run dev &
VITE_PID=$!

echo ""
echo "Development servers running:"
echo "- React app:  http://localhost:5173"
echo "- Flask API:  http://localhost:8080"
echo "Press Ctrl+C to stop both."
echo ""

wait "$FLASK_PID" "$VITE_PID"
