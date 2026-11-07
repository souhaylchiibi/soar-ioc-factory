"""Wazuh integration contract (Phase 5).

Wazuh alerts are read from the manager's alerts.json (shared volume) and
mapped to tracked IOCs the same way as Suricata's eve.json.

NOTE: the parser accepts Wazuh's JSON schema (full_log / rule / data);
verification against a live manager happens when the `wazuh` profile runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class WazuhAlert:
    timestamp: datetime
    rule_id: Optional[int]
    rule_level: Optional[int]
    description: str
    src_ip: Optional[str]
    full_log: str


def parse_alerts_json(path: Path, limit: int = 500) -> list[WazuhAlert]:
    """Parse Wazuh alerts.json (one JSON per line, newest last)."""
    alerts: list[WazuhAlert] = []
    if not path.exists():
        return alerts
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts_raw = obj.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)
        rule = obj.get("rule") or {}
        data = obj.get("data") or {}
        alerts.append(WazuhAlert(
            timestamp=ts,
            rule_id=rule.get("id"),
            rule_level=rule.get("level"),
            description=rule.get("description", ""),
            src_ip=data.get("srcip") or data.get("srcip") or obj.get("srcip"),
            full_log=obj.get("full_log", "")[:4000],
        ))
    return alerts
