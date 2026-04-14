#!/bin/bash
# Start the Arq worker for background ingestion tasks
# Usage: ./scripts/start-worker.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"
source "$SCRIPT_DIR/load-env.sh"

echo "=== Starting NotebookLX Ingestion Worker ==="

# Load .env if it exists
if [ -f .env ]; then
    load_env_file .env
fi

# Set defaults
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/notebooklx.db}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export INGESTION_QUEUE_NAME="${INGESTION_QUEUE_NAME:-notebooklx:ingestion}"
export MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
export MINIO_BUCKET="${MINIO_BUCKET:-notebooklx}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}"
export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"

echo "Configuration:"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  DATABASE_URL: $DATABASE_URL"
echo "  REDIS_URL: $REDIS_URL"
echo "  INGESTION_QUEUE_NAME: $INGESTION_QUEUE_NAME"
echo ""

# Check Redis is available
if ! redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
    echo "Error: Redis is not available at $REDIS_URL"
    echo "Start Redis first: ./scripts/start-infra.sh"
    exit 1
fi

echo "✓ Redis connection verified"
echo ""
echo "Starting Arq worker..."
echo "Worker is listening for ingestion tasks on queue: $INGESTION_QUEUE_NAME"
echo ""

ARQ_BIN="$ROOT_DIR/venv/bin/arq"
if [ -x "$ARQ_BIN" ]; then
    exec "$ARQ_BIN" services.worker.main.WorkerSettings
fi

exec arq services.worker.main.WorkerSettings
