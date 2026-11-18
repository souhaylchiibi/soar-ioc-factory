"""Authentication, authorization and HTTP hardening (Phase 8).

Runs the real FastAPI app against the migrated test database: tokens,
roles, lockout, service key, path traversal guard, rate limiting and
security headers are all exercised over HTTP.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.core.db import get_db
from app.core.middleware import limiter
from app.main import app
from app.models.account import User
from app.models.ioc import AuditLog, Ioc, IocStatus, IocType, RoleName

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture()
def client(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "test-secret-" + "x" * 40)
    monkeypatch.setattr(settings, "service_api_key", "test-service-key-0123456789abcdef")
    monkeypatch.setattr(settings, "n8n_url", "http://127.0.0.1:9")
    limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.reset()


def make_user(db, username: str, role: RoleName, active: bool = True) -> User:
    user = User(username=username, email=f"{username}@test.local",
                password_hash=security.hash_password(PASSWORD), role=role, is_active=active)
    db.add(user)
    db.commit()
    return user


def token_for(client, username: str, password: str = PASSWORD) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_ioc(db, value="198.51.100.7", status=IocStatus.MONITORED, score=60) -> Ioc:
    import hashlib
    ioc = Ioc(type=IocType.IP, value=value, raw_value=value, status=status, score=score,
              fingerprint=hashlib.sha256(f"IP:{value}".encode()).hexdigest())
    db.add(ioc)
    db.commit()
    return ioc


# --------------------------------------------------------------- authn ----
class TestAuthentication:
    def test_api_requires_authentication(self, client):
        for path in ("/api/v1/iocs", "/api/v1/iocs/stats/dashboard", "/api/v1/audit",
                     "/api/v1/system/health", "/api/v1/lifecycle/funnel"):
            assert client.get(path).status_code == 401, path

    def test_health_probes_stay_public(self, client):
        assert client.get("/health").status_code == 200

    def test_login_and_me(self, client, db):
        make_user(db, "alice", RoleName.analyst)
        headers = token_for(client, "alice")
        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert me["actor"] == "alice" and me["role"] == "analyst"
        assert me["user"]["username"] == "alice"
        assert "password_hash" not in me["user"]

    def test_bad_password_is_generic_and_audited(self, client, db):
        make_user(db, "bob", RoleName.viewer)
        r = client.post("/api/v1/auth/login", json={"username": "bob", "password": "wrong-pass"})
        assert r.status_code == 401 and r.json()["detail"] == "Identifiants invalides"
        r2 = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
        assert r2.status_code == 401 and r2.json()["detail"] == r.json()["detail"]
        failures = db.execute(select(AuditLog).where(AuditLog.action == "LOGIN",
                                                     AuditLog.success.is_(False))).scalars().all()
        assert len(failures) == 2

    def test_lockout_after_repeated_failures(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "login_max_failures", 3)
        make_user(db, "carol", RoleName.analyst)
        for _ in range(3):
            client.post("/api/v1/auth/login", json={"username": "carol", "password": "nope"})
        # even the right password is refused while locked
        r = client.post("/api/v1/auth/login", json={"username": "carol", "password": PASSWORD})
        assert r.status_code == 423

    def test_disabled_account_token_is_rejected_immediately(self, client, db):
        user = make_user(db, "dave", RoleName.analyst)
        headers = token_for(client, "dave")
        user.is_active = False
        db.commit()
        assert client.get("/api/v1/iocs", headers=headers).status_code == 401

    def test_tampered_token_rejected(self, client, db):
        make_user(db, "erin", RoleName.admin)
        headers = token_for(client, "erin")
        bad = {"Authorization": headers["Authorization"][:-2] + "xx"}
        assert client.get("/api/v1/iocs", headers=bad).status_code == 401

    def test_validation_errors_never_echo_password(self, client):
        r = client.post("/api/v1/auth/login", json={"username": "", "password": "secret-value"})
        assert r.status_code == 422
        assert "secret-value" not in r.text


# --------------------------------------------------------------- authz ----
class TestAuthorization:
    def test_viewer_reads_but_cannot_run_operations(self, client, db):
        make_user(db, "viv", RoleName.viewer)
        headers = token_for(client, "viv")
        assert client.get("/api/v1/iocs", headers=headers).status_code == 200
        assert client.post("/api/v1/iocs/expire/run", headers=headers).status_code == 403
        assert client.get("/api/v1/users", headers=headers).status_code == 403

    def test_analyst_transition_uses_token_identity_not_body(self, client, db):
        make_user(db, "ana", RoleName.analyst)
        ioc = make_ioc(db)
        headers = token_for(client, "ana")
        r = client.post(f"/api/v1/iocs/{ioc.id}/transition", headers=headers,
                        json={"to_status": "REVIEW_REQUIRED", "reason": "manual triage",
                              "actor": "someone-else"})
        assert r.status_code == 200, r.text
        assert r.json()["actor"] == "ana"
        entry = db.execute(select(AuditLog).where(AuditLog.action == "TRANSITION")).scalar_one()
        assert entry.actor == "ana"

    def test_analyst_cannot_manage_users(self, client, db):
        make_user(db, "ann", RoleName.analyst)
        headers = token_for(client, "ann")
        r = client.post("/api/v1/users", headers=headers,
                        json={"username": "x1", "email": "x1@t.l", "password": PASSWORD})
        assert r.status_code == 403

    def test_admin_user_lifecycle(self, client, db):
        make_user(db, "root", RoleName.admin)
        headers = token_for(client, "root")
        weak = client.post("/api/v1/users", headers=headers,
                           json={"username": "weak", "email": "w@t.l", "password": "aaaaaaaaaaaa"})
        assert weak.status_code == 422
        r = client.post("/api/v1/users", headers=headers,
                        json={"username": "newbie", "email": "n@t.l", "password": PASSWORD, "role": "viewer"})
        assert r.status_code == 201
        uid = r.json()["id"]
        assert client.post("/api/v1/users", headers=headers, json={
            "username": "newbie", "email": "n2@t.l", "password": PASSWORD}).status_code == 409
        r = client.patch(f"/api/v1/users/{uid}", headers=headers, json={"role": "analyst"})
        assert r.status_code == 200 and r.json()["role"] == "analyst"
        actions = {a.action for a in db.execute(select(AuditLog)).scalars()}
        assert {"USER_CREATE", "USER_UPDATE"} <= actions

    def test_last_admin_cannot_demote_itself(self, client, db):
        admin = make_user(db, "solo", RoleName.admin)
        headers = token_for(client, "solo")
        r = client.patch(f"/api/v1/users/{admin.id}", headers=headers, json={"role": "viewer"})
        assert r.status_code == 409


# ------------------------------------------------------------- service ----
class TestServiceKey:
    def test_service_key_runs_operations_with_workflow_actor(self, client, db):
        r = client.post("/api/v1/iocs/expire/run",
                        headers={"X-API-Key": settings.service_api_key, "X-Actor": "workflow-7"})
        assert r.status_code == 200, r.text
        batch = db.execute(select(AuditLog).where(AuditLog.action == "EXPIRE",
                                                  AuditLog.entity_type == "batch")).scalar_one()
        assert batch.actor == "workflow-7"
        assert isinstance(batch.detail["duration_ms"], int)

    def test_service_actor_label_cannot_impersonate_a_user(self, client, db):
        client.post("/api/v1/iocs/expire/run",
                    headers={"X-API-Key": settings.service_api_key, "X-Actor": "admin"})
        batch = db.execute(select(AuditLog).where(AuditLog.action == "EXPIRE")).scalar_one()
        assert batch.actor == "service/admin"

    def test_wrong_service_key_rejected(self, client):
        r = client.post("/api/v1/iocs/expire/run", headers={"X-API-Key": "nope"})
        assert r.status_code == 401

    def test_service_key_disabled_when_unset(self, client, monkeypatch):
        monkeypatch.setattr(settings, "service_api_key", "")
        assert client.get("/api/v1/iocs", headers={"X-API-Key": "anything"}).status_code == 401


# ------------------------------------------------------------ hardening ---
class TestHardening:
    def test_sensor_path_traversal_refused(self, client, db):
        make_user(db, "an2", RoleName.analyst)
        headers = token_for(client, "an2")
        for path in ("/etc/passwd", "/sensor/../etc/passwd", "C:/Windows/win.ini"):
            r = client.post("/api/v1/iocs/detections/ingest", headers=headers,
                            params={"sensor": "suricata", "path": path})
            assert r.status_code == 400, (path, r.text)

    def test_security_headers_present(self, client):
        r = client.get("/health")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"

    def test_login_rate_limited(self, client, monkeypatch):
        # Middleware reads the limit at app build time; drive the limiter directly
        # with the configured budget instead of rebuilding the app.
        statuses = [client.post("/api/v1/auth/login", json={"username": "x", "password": "y"}).status_code
                    for _ in range(settings.login_rate_limit_per_minute + 2)]
        assert 429 in statuses

    def test_production_config_guard(self, monkeypatch):
        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "secret_key", "change-me-in-production")
        monkeypatch.setattr(settings, "auth_enabled", False)
        errors = settings.production_errors()
        assert any("SECRET_KEY" in e for e in errors)
        assert any("AUTH_ENABLED" in e for e in errors)

    def test_password_policy(self):
        assert security.password_policy_error("short") is not None
        assert security.password_policy_error("alllowercaseletters") is not None
        assert security.password_policy_error(PASSWORD) is None
