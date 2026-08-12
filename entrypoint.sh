#!/bin/sh
set -e

echo "JellyNews starting..."

# Auto-run Alembic migrations
cd /app
python -m alembic upgrade head || echo "Warning: migrations may have failed (non-fatal)"

exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
