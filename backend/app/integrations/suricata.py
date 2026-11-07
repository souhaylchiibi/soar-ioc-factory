"""Suricata integration — parse eve.json alerts and map them to tracked IOCs.

Used by workflow 6 (monitoring): alerts produced by the IDS are matched
against the local inventory; unknown indicators are reported as "not tracked"
(never added silently — collection owns ingestion).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class SuricataAlert:
    timestamp: datetime
    src_ip: str
    dest_ip: str
    dest_port: Optional[int]
    signature: str
    sid: Optional[int]
    severity: Optional[int]
    raw: dict[str, Any] = field(default_factory=dict)


def parse_eve(path: Path) -> list[SuricataAlert]:
    """Read alerts from an eve.json file (one JSON object per line)."""
    alerts: list[SuricataAlert] = []
    if not path.exists():
        return alerts
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate partial lines
        if obj.get("event_type") != "alert":
            continue
        alert = obj.get("alert") or {}
        ts_raw = obj.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)
        alerts.append(SuricataAlert(
            timestamp=ts,
            src_ip=obj.get("src_ip", ""),
            dest_ip=obj.get("dest_ip", ""),
            dest_port=obj.get("dest_port"),
            signature=alert.get("signature", ""),
            sid=alert.get("signature_id"),
            severity=alert.get("severity"),
            raw=obj,
        ))
    return alerts


def trackable_value(alert: SuricataAlert) -> Optional[str]:
    """The indicator value this alert evidences (IP side of the alert)."""
    return alert.dest_ip or alert.src_ip or None
