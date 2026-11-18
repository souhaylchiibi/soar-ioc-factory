"""Phase 2 — socle : healthchecks, config, logging.

Ces tests tournent contre l'application importable ; /ready nécessite
PostgreSQL (lancé via docker compose) et est marqué `skip` sinon.
"""
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.logging import JsonFormatter, setup_logging
from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    def test_health_returns_200(self) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_ready_reports_database_status(self) -> None:
        resp = client.get("/ready")
        # 200 = DB up, 503 = DB down; the body always carries the detail.
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert body["status"] in ("ready", "degraded")
        assert "database" in body
        if resp.status_code == 500:  # pragma: no cover
            pytest.fail("internal error leaked by /ready")

    def test_openapi_document_available(self) -> None:
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["info"]["title"] == "SOAR IOC Factory"


class TestConfiguration:
    def test_settings_load_from_environment(self) -> None:
        s = Settings(postgres_host="db", postgres_password="x")
        assert s.database_url.startswith("postgresql+psycopg://soar:x@db:5432/")

    def test_scoring_thresholds_are_configurable_and_ordered(self) -> None:
        s = get_settings()
        assert 0 <= s.score_threshold_monitor < s.score_threshold_publish <= 100

    def test_cors_origins_parsed(self) -> None:
        s = Settings(cors_origins="http://a, http://b ,")
        assert s.cors_origins_list == ["http://a", "http://b"]


class TestLogging:
    def test_json_formatter_emits_one_json_object(self) -> None:
        import json

        setup_logging("INFO")
        logger = logging.getLogger("test.json")
        record = logging.LogRecord(
            name="test.json",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        record.action = "unit_test"
        line = JsonFormatter().format(record)
        payload = json.loads(line)
        assert payload["message"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["action"] == "unit_test"
        assert "ts" in payload
