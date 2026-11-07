#!/bin/bash
# Add a localfile entry so Wazuh reads the LAB log (idempotent).
set -e
CONF=/var/ossec/etc/ossec.conf

if grep -q "/lab-logs/access.log" "$CONF"; then
  echo "localfile deja present"
  exit 0
fi

TMP=$(mktemp)
awk '
  /<\/ossec_config>/ && !done {
    print "  <localfile>"
    print "    <log_format>syslog</log_format>"
    print "    <location>/lab-logs/access.log</location>"
    print "  </localfile>"
    done=1
  }
  { print }
' "$CONF" > "$TMP"
# Ownership MUST stay root:wazuh (wazuh-db runs as user `wazuh`).
cat "$TMP" > "$CONF"
rm -f "$TMP"
chown root:wazuh "$CONF"
chmod 640 "$CONF"
echo "localfile ajoute"
grep -A3 "/lab-logs/access.log" "$CONF"
