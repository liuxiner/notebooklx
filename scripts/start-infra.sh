#!/bin/bash
# Start infrastructure services (Redis and MinIO)
# Usage: ./scripts/start-infra.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/load-env.sh"

if [ -f "$ROOT_DIR/.env" ]; then
    load_env_file "$ROOT_DIR/.env"
fi

export MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
export MINIO_BUCKET="${MINIO_BUCKET:-notebooklx}"
export PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"

echo "=== Starting Infrastructure Services ==="

# Check if Redis is already running
if lsof -i :6379 >/dev/null 2>&1; then
    echo "Redis already running on port 6379"
else
    echo "Starting Redis..."
    if command -v redis-server &> /dev/null; then
        redis-server --daemonize yes --port 6379
        echo "Redis started via redis-server"
    else
        docker run -d --name notebooklx-redis -p 6379:6379 redis:7-alpine 2>/dev/null || \
        docker start notebooklx-redis 2>/dev/null || \
        echo "Warning: Could not start Redis. Please start it manually."
    fi
fi

# Check if MinIO is already running
if lsof -i :9000 >/dev/null 2>&1; then
    echo "MinIO already running on port 9000"
else
    echo "Starting MinIO..."
    docker run -d --name notebooklx-minio \
        -p 9000:9000 -p 9001:9001 \
        -e MINIO_ROOT_USER=minioadmin \
        -e MINIO_ROOT_PASSWORD=minioadmin \
        minio/minio server /data --console-address ":9001" 2>/dev/null || \
    docker start notebooklx-minio 2>/dev/null || \
    echo "Warning: Could not start MinIO. Please start it manually."
fi

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 2

# Verify Redis
if redis-cli ping >/dev/null 2>&1; then
    echo "✓ Redis is ready"
else
    echo "✗ Redis not responding"
fi

# Verify MinIO
if curl -s http://localhost:9000/minio/health/live >/dev/null 2>&1; then
    echo "✓ MinIO is ready"

    # Create bucket if mc is available
    if command -v mc &> /dev/null; then
        mc alias set local "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null 2>&1
        mc mb "local/$MINIO_BUCKET" --ignore-existing >/dev/null 2>&1
        echo "✓ MinIO bucket '$MINIO_BUCKET' ready"
    elif [ -x "$PYTHON_BIN" ]; then
        MINIO_ENDPOINT="$MINIO_ENDPOINT" \
        MINIO_ACCESS_KEY="$MINIO_ACCESS_KEY" \
        MINIO_SECRET_KEY="$MINIO_SECRET_KEY" \
        MINIO_BUCKET="$MINIO_BUCKET" \
        "$PYTHON_BIN" - <<'PY'
import os

import boto3
from botocore.exceptions import ClientError

endpoint_url = os.environ["MINIO_ENDPOINT"]
access_key = os.environ["MINIO_ACCESS_KEY"]
secret_key = os.environ["MINIO_SECRET_KEY"]
bucket_name = os.environ["MINIO_BUCKET"]

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint_url,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
)

try:
    s3.head_bucket(Bucket=bucket_name)
except ClientError as exc:
    error_code = exc.response.get("Error", {}).get("Code", "")
    if error_code not in {"404", "NoSuchBucket"}:
        raise
    s3.create_bucket(Bucket=bucket_name)
PY
        echo "✓ MinIO bucket '$MINIO_BUCKET' ready"
    else
        echo "Note: Install 'mc' or configure PYTHON_BIN to auto-create bucket"
    fi
else
    echo "✗ MinIO not responding"
fi

echo ""
echo "Infrastructure ready!"
echo "  Redis:  redis://localhost:6379"
echo "  MinIO:  http://localhost:9000 (console: http://localhost:9001)"
