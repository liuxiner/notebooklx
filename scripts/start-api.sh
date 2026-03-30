#!/bin/bash
# Start the FastAPI server
# Usage: ./scripts/start-api.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"
source "$SCRIPT_DIR/load-env.sh"

echo "=== Starting NotebookLX API Server ==="

# Load .env if it exists
if [ -f .env ]; then
    load_env_file .env
fi

# Set defaults
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/notebooklx.db}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
export MINIO_BUCKET="${MINIO_BUCKET:-notebooklx}"

echo "Configuration:"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  DATABASE_URL: $DATABASE_URL"
echo "  REDIS_URL: $REDIS_URL"
echo "  MINIO_ENDPOINT: $MINIO_ENDPOINT"
echo ""

# Run migrations
echo "Running database migrations..."
cd "$ROOT_DIR/services/api"
alembic upgrade head 2>/dev/null || echo "Warning: Migrations may have failed or already applied"
cd "$ROOT_DIR"

echo ""
echo "Starting uvicorn server..."
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""

exec uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000
