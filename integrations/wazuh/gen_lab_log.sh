#!/bin/bash
# Generate SYNTHETIC lab access-log lines mentioning tracked IOC IPs.
# Format: syslog-style sshd brute force from the published indicator.
# This is LAB DATA (clearly labelled), used to exercise Wazuh rules.
set -e
TARGET_IP="${1:?usage: gen_lab_log.sh <ip> <count>}"
COUNT="${2:-10}"
LOG=/lab-logs/access.log
mkdir -p "$(dirname "$LOG")"
for i in $(seq 1 "$COUNT"); do
  TS=$(date '+%b %d %H:%M:%S')
  echo "$TS lab-fw sshd[2043]: Failed password for invalid user admin from $TARGET_IP port $((40000 + i)) ssh2" >> "$LOG"
  echo "$TS lab-fw sshd[2043]: error: maximum authentication attempts exceeded for invalid user admin from $TARGET_IP port $((40000 + i)) ssh2" >> "$LOG"
done
echo "ecritures: $((COUNT * 2)) lignes -> $LOG (source=$TARGET_IP)"
