#!/bin/bash
# Apply Alembic migrations on the deployed stack (idempotent).
# Runs inside a short-lived python:3.11-slim container on the compose network
# so the server needs no Python toolchain.
set -euo pipefail
cd /home/ubuntu/soar-ioc-factory

# Read DB settings from .env (never echoed).
# The .env comes from Windows: strip CR before sourcing (CRLF-safe).
tr -d '\r' < .env > /tmp/.env.lf
set -a
. /tmp/.env.lf
set +a
rm -f /tmp/.env.lf

NET=$(sudo docker network ls --format '{{.Name}}' | grep 'soar-net' | head -1)
echo "reseau: $NET"

URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"

sudo docker run --rm \
  --network "$NET" \
  -v /home/ubuntu/soar-ioc-factory:/work \
  -w /work/backend \
  -e DATABASE_URL="$URL" \
  -e PYTHONPATH=/work/backend \
  python:3.11-slim \
  bash -c "pip install -q -r requirements.txt && python -m alembic upgrade head && python -m alembic current"

echo "== migration terminee =="
