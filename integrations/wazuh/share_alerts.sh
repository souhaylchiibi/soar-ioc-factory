#!/bin/bash
# Make Wazuh alerts.json readable for the API container (LAB only).
# Wazuh recreates the file on rotation with 640 — re-run after restarts.
set -e
DIR=/var/ossec/logs/alerts
chmod a+rx "$DIR"
find "$DIR" -maxdepth 1 -name "alerts.json*" -exec chmod a+r {} \; 2>/dev/null || true
ls -la "$DIR" | head -5
echo "lecture ouverte pour le conteneur API (volume soar_wazuh_alerts)"
