#!/usr/bin/env bash
# start_new_ui.sh — Start the React + FastAPI stack with logging.
#
# Usage:
#   ./start_new_ui.sh          # Start both servers (logs go to logs/)
#   ./start_new_ui.sh stop     # Stop both servers
#
# Log files:
#   logs/uvicorn.log           # FastAPI backend log
#   logs/vite.log              # React dev server log

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
UVICORN_LOG="$LOG_DIR/uvicorn.log"
VITE_LOG="$LOG_DIR/vite.log"
UVICORN_PID_FILE="$LOG_DIR/uvicorn.pid"
VITE_PID_FILE="$LOG_DIR/vite.pid"

# ─── STOP ────────────────────────────────────────────────────────────────────
stop_servers() {
    echo "Stopping servers..."
    if [ -f "$UVICORN_PID_FILE" ]; then
        PID=$(cat "$UVICORN_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "  Stopped uvicorn (PID $PID)"
        fi
        rm -f "$UVICORN_PID_FILE"
    fi
    if [ -f "$VITE_PID_FILE" ]; then
        PID=$(cat "$VITE_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "  Stopped vite (PID $PID)"
        fi
        rm -f "$VITE_PID_FILE"
    fi
    echo "Done."
}

if [ "$1" = "stop" ]; then
    stop_servers
    exit 0
fi

# ─── START ───────────────────────────────────────────────────────────────────
# Stop any existing instances first
stop_servers 2>/dev/null

mkdir -p "$LOG_DIR"

echo "Starting FastAPI backend..."
echo "--- uvicorn started at $(date) ---" >> "$UVICORN_LOG"
(cd "$SCRIPT_DIR" && uvicorn api.main:app --reload --port 8000 --ws none \
    >> "$UVICORN_LOG" 2>&1) &
echo $! > "$UVICORN_PID_FILE"
echo "  PID $(cat "$UVICORN_PID_FILE") → $UVICORN_LOG"

echo "Starting React dev server..."
echo "--- vite started at $(date) ---" >> "$VITE_LOG"
# Run vite directly; redirect output to log file.
# Note: Vite buffers output when not connected to a terminal,
# so the log may lag behind real-time. Use 'lsof -i :5173' to check if running.
(cd "$SCRIPT_DIR/frontend" && npx vite >> "$VITE_LOG" 2>&1) &
echo $! > "$VITE_PID_FILE"
echo "  PID $(cat "$VITE_PID_FILE") → $VITE_LOG"

# Wait for servers to be ready
sleep 5

# Health check
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✓ FastAPI running at http://localhost:8000"
else
    echo "✗ FastAPI failed to start — check $UVICORN_LOG"
fi

# Vite may need a bit longer to compile
VITE_OK=false
for i in 1 2 3; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        VITE_OK=true
        break
    fi
    sleep 2
done
if $VITE_OK; then
    echo "✓ React UI running at http://localhost:5173"
else
    echo "✗ Vite may still be starting — check $VITE_LOG"
fi

echo ""
echo "Log files:"
echo "  tail -f $UVICORN_LOG"
echo "  tail -f $VITE_LOG"
echo ""
echo "Stop with: ./start_new_ui.sh stop"
