#!/bin/bash
# Deploy the SOAR stack on the EC2 lab instance (no public ports).
set -euo pipefail
cd /home/ubuntu/soar-ioc-factory

echo "== preflight =="
command -v sudo >/dev/null
test -f .env && echo ".env present"
sudo docker --version
sudo docker compose version

echo "== demarrage du stack - profil n8n, override aws =="
sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml --profile n8n up -d --build

echo "== etat des conteneurs =="
sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml --profile n8n ps

echo "== wait healthy =="
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
    echo "frontend+api up apres ${i} x 5s"
    break
  fi
  sleep 5
done

echo "== verification finale =="
echo "-- /health (nginx -> api) :"
curl -fsS http://127.0.0.1/health || echo ECHEC
echo
echo "-- /ready :"
curl -fsS http://127.0.0.1/ready || echo ECHEC
echo
echo "-- /api/v1/system/health :"
curl -fsS http://127.0.0.1/api/v1/system/health | head -c 400 || echo ECHEC
echo
echo "-- ports ecoutes (attendu: 127.0.0.1 uniquement hors ssh) :"
sudo ss -tlnp | grep -E ':(80|8000|5432|5678)\s' || true
