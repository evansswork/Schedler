#!/bin/sh
set -e
# Data and media live on mounted volumes (/app/data, /app/media).
mkdir -p /app/data /app/media/public
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 \
    --proxy-headers --forwarded-allow-ips='*'
