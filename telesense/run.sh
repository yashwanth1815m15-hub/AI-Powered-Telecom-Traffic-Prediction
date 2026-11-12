#!/usr/bin/env bash
# TeleSense 1-Click Launch Script
# Starts FastAPI Backend (port 8000) and Vite React Frontend (port 3000)

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PYTHON_BIN="/Users/yashu/.gemini/antigravity-ide/scratch/module1_preprocessing/.venv/bin/python"

echo "=========================================================="
echo "📡 Launching TeleSense AI Telecom Traffic & Network Planner"
echo "=========================================================="

# 1. Start FastAPI Backend
echo "Starting Backend on http://localhost:8000..."
cd "$DIR/backend"
PYTHONPATH=.:.. "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Trap Ctrl+C to kill both services
trap "kill $BACKEND_PID; exit" INT TERM EXIT

# 2. Start Vite Frontend
echo "Starting Frontend on http://localhost:3000..."
cd "$DIR/frontend"
npm run dev -- --host 0.0.0.0 --port 3000

wait $BACKEND_PID
