#!/bin/bash
# RoboTaste Launcher — double-click to start all services with pump

PROJECT_DIR="/Users/alonnissan/Library/Mobile Documents/com~apple~CloudDocs/University/Masters/Research/RoboTaste/Software"

cd "$PROJECT_DIR" || { echo "ERROR: Could not cd to project directory"; read -r; exit 1; }

# Find Python: venv > conda base > system python3
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
elif [ -f "/Users/alonnissan/anaconda3/bin/python3" ]; then
    PYTHON="/Users/alonnissan/anaconda3/bin/python3"
else
    PYTHON="python3"
fi

echo "Using Python: $PYTHON"
echo "Project: $PROJECT_DIR"
echo ""

# Start the launcher in foreground; capture its PID
"$PYTHON" "$PROJECT_DIR/start_new_ui.py" --with-pump &
PY_PID=$!

# Forward SIGHUP (Terminal window closed) and SIGTERM as SIGINT to Python,
# so its cleanup() handler runs and all child services are properly shut down.
cleanup() {
    echo ""
    echo "Forwarding shutdown signal to RoboTaste..."
    kill -INT "$PY_PID" 2>/dev/null
    wait "$PY_PID" 2>/dev/null
    exit 0
}
trap cleanup HUP INT TERM

wait "$PY_PID"
