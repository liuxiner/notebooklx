#!/bin/bash
# Start all development services (infrastructure, API, and worker)
# Usage: ./scripts/start-dev.sh
#
# This script starts:
#   1. Infrastructure (Redis + MinIO)
#   2. API server (in background or new terminal)
#   3. Worker (in background or new terminal)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"
source "$SCRIPT_DIR/load-env.sh"

echo "========================================"
echo "  NotebookLX Development Environment   "
echo "========================================"
echo ""

# Load .env if it exists
if [ -f .env ]; then
    load_env_file .env
fi

# Step 1: Start infrastructure
echo "Step 1: Starting infrastructure..."
"$SCRIPT_DIR/start-infra.sh"
echo ""

# Step 2: Check if we should use tmux/screen or run in foreground
if [ "$1" = "--foreground" ] || [ "$1" = "-f" ]; then
    echo "Running in foreground mode..."
    echo "Starting API and Worker in background..."

    # Start API in background
    "$SCRIPT_DIR/start-api.sh" > "$ROOT_DIR/logs/api.log" 2>&1 &
    API_PID=$!
    echo "API started (PID: $API_PID, logs: logs/api.log)"

    # Start Worker in background
    "$SCRIPT_DIR/start-worker.sh" > "$ROOT_DIR/logs/worker.log" 2>&1 &
    WORKER_PID=$!
    echo "Worker started (PID: $WORKER_PID, logs: logs/worker.log)"

    # Save PIDs for stop script
    mkdir -p "$ROOT_DIR/logs"
    echo "$API_PID" > "$ROOT_DIR/logs/api.pid"
    echo "$WORKER_PID" > "$ROOT_DIR/logs/worker.pid"

    echo ""
    echo "All services started!"
    echo "  API: http://localhost:8000 (docs: http://localhost:8000/docs)"
    echo "  MinIO Console: http://localhost:9001"
    echo ""
    echo "View logs:"
    echo "  tail -f logs/api.log"
    echo "  tail -f logs/worker.log"
    echo ""
    echo "Stop all services:"
    echo "  ./scripts/stop-dev.sh"

elif command -v tmux &> /dev/null; then
    echo "Step 2: Starting services in tmux session 'notebooklx'..."

    # Kill existing session if exists
    tmux kill-session -t notebooklx 2>/dev/null || true

    # Create new session with infrastructure info
    tmux new-session -d -s notebooklx -n main

    # Split into 3 panes
    tmux split-window -h -t notebooklx:main
    tmux split-window -v -t notebooklx:main.1

    # Pane 0: API server
    tmux send-keys -t notebooklx:main.0 "cd '$ROOT_DIR' && ./scripts/start-api.sh" C-m

    # Pane 1: Worker
    tmux send-keys -t notebooklx:main.1 "cd '$ROOT_DIR' && ./scripts/start-worker.sh" C-m

    # Pane 2: Shell for testing
    tmux send-keys -t notebooklx:main.2 "cd '$ROOT_DIR' && echo 'Ready for testing! API: http://localhost:8000'" C-m

    echo ""
    echo "All services started in tmux session 'notebooklx'"
    echo ""
    echo "Attach to session:"
    echo "  tmux attach -t notebooklx"
    echo ""
    echo "Tmux controls:"
    echo "  Ctrl+B then D    - Detach from session"
    echo "  Ctrl+B then 0-2  - Switch panes"
    echo "  Ctrl+B then X    - Close pane"
    echo ""
    echo "Stop all services:"
    echo "  tmux kill-session -t notebooklx"
    echo "  # or use: ./scripts/stop-dev.sh"

else
    echo ""
    echo "Step 2: Manual startup required"
    echo ""
    echo "Infrastructure is ready. Now open separate terminals and run:"
    echo ""
    echo "  Terminal 1 (API):"
    echo "    cd $ROOT_DIR && ./scripts/start-api.sh"
    echo ""
    echo "  Terminal 2 (Worker):"
    echo "    cd $ROOT_DIR && ./scripts/start-worker.sh"
    echo ""
    echo "Or install tmux for automatic multi-pane setup:"
    echo "  brew install tmux"
    echo ""
fi
