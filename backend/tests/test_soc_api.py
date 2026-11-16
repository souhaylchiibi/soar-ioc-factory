"""SOC console endpoints: funnel, timeline, detection center, triage,
run history, IOC activity, search, notifications, integrations.

Every assertion compares the API output with rows inserted by the test:
nothing is allowed to appear that the database does not contain.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.soc import severity_of
from app.core import security
from app.core.config import settings
from app.core.db import get_db
from app.core.middleware import limiter
from app.lifecycle.machine import transition
from app.main import app
from app.models.account import User
from app.models.ioc import AuditLog, Detection, Ioc, IocStatus, IocType, RoleName
from app.services import integrations_status as integ

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture()
def client(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "test-secret-" + "x" * 40)
    monkeypatch.setattr(settings, "n8n_url", "http://127.0.0.1:9")
    monkeypatch.setattr(settings, "misp_url", "")
    integ._cache.update(at=0.0, value=None)
    limiter.reset()
    db.add(User(username="ana", email="ana@t.l", password_hash=security.hash_password(PASSWORD),
                role=RoleName.analyst))
    db.commit()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login", json={"username": "ana", "password": PASSWORD}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {tok}"})
    yield c
    app.dependency_overrides.clear()


def ioc(db, value, status=IocStatus.NORMALIZED, score=None, synthetic=False) -> Ioc:
    i = Ioc(type=IocType.DOMAIN, value=value, raw_value=value, status=status, score=score,
            is_synthetic=synthetic, fingerprint=hashlib.sha256(f"DOMAIN:{value}".encode()).hexdigest())
    db.add(i)
    db.flush()
    return i


def test_funnel_counts_match_lifecycle_events(client, db):
    a = ioc(db, "a.example", IocStatus.ENRICHED)
    db.add(transition(a, IocStatus.SCORED, reason="t").event)
    a.score = 85
    db.add(transition(a, IocStatus.PUBLISHED, reason="t").event)
    b = ioc(db, "b.example", IocStatus.ENRICHED)
    db.add(transition(b, IocStatus.SCORED, reason="t").event)
    db.add(AuditLog(actor="workflow-1/x", action="COLLECT", entity_type="source", entity_id="x",
                    detail={"collected": 7}, success=True))
    db.commit()

    body = client.get("/api/v1/lifecycle/funnel").json()
    stages = {s["key"]: s for s in body["stages"]}
    assert stages["collect"]["count"] == 7
    assert stages["score"]["count"] == 2
    assert stages["publish"]["count"] == 1 and stages["publish"]["current"] == 1
    assert body["decisions"]["publish"] == 1
    assert all(s["proof"] for s in body["stages"])


def test_timeline_has_one_point_per_day_and_real_counts(client, db):
    ioc(db, "t.example")
    db.commit()
    body = client.get("/api/v1/stats/timeline?days=14").json()
    assert len(body["series"]) == 14
    today = datetime.now(timezone.utc).date().isoformat()
    point = next(p for p in body["series"] if p["date"] == today)
    assert point["created"] == 1
    assert sum(p["created"] for p in body["series"]) == 1


def test_detection_center_and_triage_updates_ioc_counter(client, db):
    target = ioc(db, "evil.example", IocStatus.MONITORED, score=60)
    det = Detection(ioc_id=target.id, sensor="wazuh", rule_id="100200",
                    raw_event={"rule": {"id": 100200, "level": 10, "description": "bad domain"}},
                    matched_at=datetime.now(timezone.utc))
    db.add(det)
    db.commit()

    listing = client.get("/api/v1/detections").json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["ioc_value"] == "evil.example"
    assert item["severity"] == "high"          # derived from Wazuh level 10
    assert item["signature"] == "bad domain"
    assert item["triage"] == "pending"

    r = client.post(f"/api/v1/detections/{det.id}/review",
                    json={"verdict": "false_positive", "note": "internal scanner"})
    assert r.status_code == 200 and r.json()["triage"] == "false_positive"
    db.refresh(target)
    assert target.false_positive_count == 1
    # reverting the verdict keeps the counter consistent
    client.post(f"/api/v1/detections/{det.id}/review", json={"verdict": "confirmed"})
    db.refresh(target)
    assert target.false_positive_count == 0
    assert client.get("/api/v1/detections?triage=confirmed").json()["total"] == 1


def test_severity_only_when_sensor_states_it():
    assert severity_of("suricata", {"alert": {"severity": 1}}) == "high"
    assert severity_of("wazuh", {"rule": {"level": 13}}) == "critical"
    assert severity_of("manual", {"rule": "LAB"}) is None
    assert severity_of("wazuh", {"rule": "LAB-DEMO-1"}) is None  # manual-style payload
    assert severity_of("suricata", {}) is None


def test_workflow_runs_list_batches_with_measured_duration(client, db):
    db.add(AuditLog(actor="workflow-5", action="PUBLISH", entity_type="batch",
                    detail={"published": 2, "duration_ms": 120}))
    db.add(AuditLog(actor="ana", action="EXPIRE", entity_type="batch",
                    detail={"expired": 0}, success=False, error="boom"))
    db.add(AuditLog(actor="workflow-5", action="PUBLISH", entity_type="ioc", detail={}))  # not a run
    db.commit()
    body = client.get("/api/v1/workflows/runs").json()
    assert body["total"] == 2 and body["failed_total"] == 1
    by_actor = {r["actor"]: r for r in body["runs"]}
    assert by_actor["workflow-5"]["trigger"] == "n8n" and by_actor["workflow-5"]["duration_ms"] == 120
    assert by_actor["ana"]["trigger"] == "manuel" and by_actor["ana"]["duration_ms"] is None


def test_ioc_activity_and_search(client, db):
    target = ioc(db, "search-me.example", IocStatus.MONITORED, score=55)
    db.commit()
    act = client.get(f"/api/v1/iocs/{target.id}/activity").json()
    assert set(act) >= {"score_history", "publications", "detections", "provenance", "audit"}
    res = client.get("/api/v1/search?q=search-me").json()
    assert [i["value"] for i in res["iocs"]] == ["search-me.example"]
    assert client.get("/api/v1/search?q=x").status_code == 422


def test_notifications_surface_real_failures_only(client, db):
    assert client.get("/api/v1/notifications").json()["count"] == 0
    db.add(AuditLog(actor="workflow-1/urlhaus", action="COLLECT", entity_type="source",
                    success=False, error="401 Unauthorized"))
    db.commit()
    items = client.get("/api/v1/notifications").json()["items"]
    assert len(items) == 1 and "401" in items[0]["message"]


def test_integrations_report_missing_config_honestly(client, db):
    body = client.get("/api/v1/integrations/status?refresh=true").json()
    by_name = {i["name"]: i for i in body["items"]}
    assert by_name["postgresql"]["status"] == "connected"
    assert by_name["misp"]["status"] == "not_configured"
    assert by_name["n8n"]["status"] == "unreachable"      # nothing listens on :9
    assert by_name["suricata"]["status"] in ("no_data", "connected")


def test_manual_detection_with_string_rule_is_listed(client, db):
    """Regression: manual entries store {'rule': 'LAB-…'} (a string)."""
    target = ioc(db, "manual.example", IocStatus.MONITORED, score=60)
    db.add(Detection(ioc_id=target.id, sensor="manual", rule_id="LAB-DEMO-1",
                     raw_event={"source": "manual", "rule": "LAB-DEMO-1"}))
    db.commit()
    body = client.get("/api/v1/detections").json()
    assert body["items"][0]["signature"] is None and body["items"][0]["severity"] is None


def test_source_state_uses_audit_history_and_ignores_lab(client, db):
    """Regression: a source collected successfully (proved by audit) must
    show 'connected' even if intel_sources.last_success_at was never set,
    and the collectors summary must not report healthy when nothing works."""
    from app.models.ioc import IntelSource, SourceKind
    db.add(IntelSource(name="feodotracker", provenance_group="abuse.ch-feodo", kind=SourceKind.OPEN_SOURCE))
    db.add(IntelSource(name="blocklist_de", provenance_group="blocklist.de", kind=SourceKind.OPEN_SOURCE))
    db.add(IntelSource(name="synthetic_lab", provenance_group="lab", kind=SourceKind.SYNTHETIC))
    db.add(AuditLog(actor="workflow-1/feodotracker", action="COLLECT", entity_type="source",
                    entity_id="feodotracker", detail={"collected": 3}, success=True))
    db.commit()
    sources = {s["name"]: s for s in client.get("/api/v1/sources").json()["sources"]}
    assert sources["feodotracker"]["connection"] == "connected"
    assert sources["feodotracker"]["last_success_at"] is not None
    assert sources["blocklist_de"]["connection"] == "no_data"
    integ = client.get("/api/v1/integrations/status?refresh=true").json()
    collectors = next(i for i in integ["items"] if i["name"] == "collectors")
    assert collectors["status"] == "degraded"          # 1 of 2 real sources works
    assert collectors["detail"].startswith("1/2")       # lab source not counted
