#!/bin/sh
set -e

# Download models from Railway bucket if not already cached on volume
python download_models.py

# Start the API server
exec uvicorn app.main:app --host 0.0.0.0 --port 8001
