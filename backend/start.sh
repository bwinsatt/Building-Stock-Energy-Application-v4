#!/bin/sh
set -e

# Download models from Railway bucket if not already cached on volume
# -u forces unbuffered output so logs appear in Railway
python -u download_models.py

# Start the API server
exec uvicorn app.main:app --host 0.0.0.0 --port 8001
