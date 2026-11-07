#!/bin/bash
# Install Docker Engine (official repo) on the EC2 lab instance.
# Read-only wrt existing data: installs packages only, creates no AWS resource.
set -euo pipefail

if command -v docker >/dev/null 2>&1; then
  echo "docker deja installe: $(docker --version)"
  exit 0
fi

echo "== installation Docker Engine (repo officiel) =="
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt-get update -qq
sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# The default ubuntu user can run docker without sudo (newgrp not needed for
# scripts because we invoke `sudo docker` when necessary).
sudo usermod -aG docker ubuntu || true

echo "== verification =="
docker --version
sudo docker version --format 'server={{.Server.Version}}'
sudo docker compose version
echo "== statut =="
sudo systemctl is-enabled docker && sudo systemctl is-active docker && echo "docker actif"
