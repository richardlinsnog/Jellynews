





#!/bin/sh
set -e

# ── JellyNews Entrypoint ──────────────────────────────────────────
# Runs before the application starts:
#   1. Ensure data directory exists with correct permissions
#   2. Wait for database file to be writable
#   3. Alembic migrations are handled by the app lifespan (idempotent)
#   4. Exec the actual command (defaults to uvicorn)

DATA_DIR="${DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"

# Verify we can write to the data directory
if [ ! -w "$DATA_DIR" ]; then
    echo "ERROR: Cannot write to data directory: $DATA_DIR" >&2
    exit 1
fi

echo "JellyNews entrypoint — data dir ready: $DATA_DIR"

# Execute the command passed as arguments
exec "$@"




