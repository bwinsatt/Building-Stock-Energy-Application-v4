#!/bin/sh
set -e

# Download models if not already cached on persistent storage
python -u download_models.py

# Create database directory if it doesn't exist
mkdir -p "$(dirname "${DATABASE_PATH:-/home/data/buildingstock.db}")"

# Start the API server
# WEB_CONCURRENCY=1 for B1 (1.75 GB RAM); increase for larger SKUs
exec gunicorn \
    -w "${WEB_CONCURRENCY:-1}" \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8001 \
    --timeout "${GUNICORN_TIMEOUT:-300}" \
    app.main:app
