#!/bin/bash
# Seed the deployed instance with REAL threat intelligence (no fabricated data):
#   1. register intel sources
#   2. collect (OTX + feodo + blocklist.de + urlscan) through the local API
#   3. enrich (OTX + AbuseIPDB)  4. score  5. show stats
set -euo pipefail
cd /home/ubuntu/soar-ioc-factory

tr -d '\r' < .env > /tmp/.env.lf && set -a && . /tmp/.env.lf && set +a && rm -f /tmp/.env.lf
NET=$(sudo docker network ls --format '{{.Name}}' | grep 'soar-net' | head -1)

echo "== 1. enregistrement des sources =="
sudo docker run --rm --network "$NET" \
  -v /home/ubuntu/soar-ioc-factory:/work -w /work \
  -e PYTHONPATH=/work/backend -e POSTGRES_HOST=db \
  -e POSTGRES_USER="$POSTGRES_USER" -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  python:3.11-slim \
  bash -c "pip install -q -r backend/requirements.txt && python scripts/register_sources.py" | tail -12

echo "== 2. collecte reelle depuis EC2 =="
curl -fsS -X POST "http://127.0.0.1/api/v1/iocs/collect/run?limit=30" | head -c 500
echo

echo "== 3. enrichissement (OTX + AbuseIPDB) =="
curl -fsS -X POST "http://127.0.0.1/api/v1/iocs/enrich/run?limit=25" | head -c 350
echo

echo "== 4. scoring =="
curl -fsS -X POST "http://127.0.0.1/api/v1/iocs/scoring/run" \
  -H 'Content-Type: application/json' -d '{"ioc_ids":[],"only_status":null}' | head -c 300
echo

echo "== 5. statistiques finales =="
curl -fsS "http://127.0.0.1/api/v1/iocs/stats/dashboard" | head -c 500
echo
