#!/bin/bash
# Stop all development services
# Usage: ./scripts/stop-dev.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Stopping NotebookLX Development Services ==="

# Stop tmux session if exists
if tmux has-session -t notebooklx 2>/dev/null; then
    echo "Stopping tmux session 'notebooklx'..."
    tmux kill-session -t notebooklx
    echo "✓ Tmux session stopped"
fi

# Stop background processes using PID files
if [ -f "$ROOT_DIR/logs/api.pid" ]; then
    API_PID=$(cat "$ROOT_DIR/logs/api.pid")
    if kill -0 "$API_PID" 2>/dev/null; then
        echo "Stopping API server (PID: $API_PID)..."
        kill "$API_PID" 2>/dev/null || true
        echo "✓ API server stopped"
    fi
    rm -f "$ROOT_DIR/logs/api.pid"
fi

if [ -f "$ROOT_DIR/logs/worker.pid" ]; then
    WORKER_PID=$(cat "$ROOT_DIR/logs/worker.pid")
    if kill -0 "$WORKER_PID" 2>/dev/null; then
        echo "Stopping worker (PID: $WORKER_PID)..."
        kill "$WORKER_PID" 2>/dev/null || true
        echo "✓ Worker stopped"
    fi
    rm -f "$ROOT_DIR/logs/worker.pid"
fi

# Stop Docker containers
echo ""
echo "Stopping Docker containers..."

if docker ps -q -f name=notebooklx-redis 2>/dev/null | grep -q .; then
    docker stop notebooklx-redis >/dev/null 2>&1
    echo "✓ Redis container stopped"
fi

if docker ps -q -f name=notebooklx-minio 2>/dev/null | grep -q .; then
    docker stop notebooklx-minio >/dev/null 2>&1
    echo "✓ MinIO container stopped"
fi

# Stop Homebrew Redis if running
if command -v brew &> /dev/null; then
    if brew services list 2>/dev/null | grep -q "redis.*started"; then
        echo "Stopping Homebrew Redis..."
        brew services stop redis >/dev/null 2>&1
        echo "✓ Homebrew Redis stopped"
    fi
fi

echo ""
echo "All services stopped."
echo ""
echo "Note: To also remove Docker containers, run:"
echo "  docker rm notebooklx-redis notebooklx-minio"
