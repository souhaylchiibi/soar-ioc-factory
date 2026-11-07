"""Phase 5 (option B) — MISP client + operations, fully mocked (no network).

Covers: auth headers, event/attribute lifecycle, read-back verification,
retraction confirmation, unconfigured/ outage honesty paths.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.integrations.misp import MISP_ATTRIBUTE_TYPE, MispClient, MispError
from app.models.ioc import AuditLog, Ioc, IocStatus, IocType, Publication
from app.services import misp_ops
from sqlalchemy import select


def make_ioc(value: str = "203.0.113.9", ioc_type: IocType = IocType.IP,
             status: IocStatus = IocStatus.PUBLISHED, score: int = 85) -> Ioc:
    import uuid
    from datetime import datetime, timezone
    return Ioc(type=ioc_type, value=value, raw_value=value, status=status,
               score=score, fingerprint="f" * 64, id=uuid.uuid4(),
               first_seen_at=datetime.now(timezone.utc),
               last_seen_at=datetime.now(timezone.utc))


# --------------------------------------------------------- mock MISP ------
class FakeMisp:
    """Scripted in-memory MISP API (httpx.MockTransport handler)."""

    def __init__(self, fail_auth: bool = False, drop_delete: bool = False,
                 hide_view: bool = False):
        self.fail_auth = fail_auth
        self.drop_delete = drop_delete      # delete returns success but value stays
        self.hide_view = hide_view          # view returns 404 always
        self.calls: list[str] = []
        self.attributes: dict[str, dict] = {}
        self._next_attr = 100

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        auth = request.headers.get("Authorization", "")
        if self.fail_auth or auth != "k" * 32:
            return httpx.Response(401, json={"error": "Authentication failed."})

        path, method = request.url.path, request.method
        if path == "/servers/getVersion":
            return httpx.Response(200, json={"version": "2.4.165"})
        if path == "/events/add" and method == "POST":
            return httpx.Response(200, json={"Event": {"id": "7"}})
        if path == "/events/7/publish" and method == "POST":
            return httpx.Response(200, json={"message": "Event published."})
        if path == "/attributes/add" and method == "POST":
            body = json.loads(request.content.decode())
            attr = body["Attribute"]
            self._next_attr += 1
            aid = str(self._next_attr)
            self.attributes[aid] = {"id": aid, "value": attr["value"],
                                    "type": attr["type"], "to_ids": attr["to_ids"]}
            return httpx.Response(200, json={"Attribute": {"id": aid}})
        if path.startswith("/attributes/view/") and method == "GET":
            aid = path.rsplit("/", 1)[-1]
            if self.hide_view or aid not in self.attributes:
                return httpx.Response(404, json={"error": "Attribute not found."})
            return httpx.Response(200, json={"Attribute": self.attributes[aid]})
        if path.startswith("/attributes/delete/") and method == "DELETE":
            aid = path.rsplit("/", 1)[-1]
            if not self.drop_delete:
                self.attributes.pop(aid, None)
            return httpx.Response(200, json={"message": "Attribute deleted."})
        return httpx.Response(404, json={"error": f"unknown {method} {path}"})


def client_with(fake: FakeMisp) -> MispClient:
    return MispClient(base_url="https://misp.lab", api_key="k" * 32,
                      transport=httpx.MockTransport(fake.handler))


# ------------------------------------------------------------ client -------
class TestMispClient:
    def test_requires_url_and_key(self) -> None:
        with pytest.raises(ValueError, match="base_url and api_key"):
            MispClient(base_url="", api_key="")

    def test_health_returns_version_and_sends_auth(self) -> None:
        fake = FakeMisp()
        assert client_with(fake).health() == "2.4.165"
        assert any("getVersion" in c for c in fake.calls)

    def test_bad_auth_is_a_clear_error(self) -> None:
        fake = FakeMisp(fail_auth=True)
        with pytest.raises(MispError, match="auth refused"):
            client_with(fake).health()

    def test_event_created_once_then_cached(self) -> None:
        fake = FakeMisp()
        c = client_with(fake)
        assert c.ensure_event() == "7"
        assert c.ensure_event() == "7"
        assert sum(1 for x in fake.calls if x == "POST /events/add") == 1

    @pytest.mark.parametrize("ioc_type,misp_type", [
        (IocType.IP, "ip-src"), (IocType.DOMAIN, "domain"), (IocType.URL, "url"),
        (IocType.HASH_MD5, "md5"), (IocType.HASH_SHA1, "sha1"),
        (IocType.HASH_SHA256, "sha256"),
    ])
    def test_attribute_type_mapping(self, ioc_type: IocType, misp_type: str) -> None:
        assert MISP_ATTRIBUTE_TYPE[ioc_type] == misp_type
        fake = FakeMisp()
        c = client_with(fake)
        aid = c.add_attribute(make_ioc(ioc_type=ioc_type))
        assert fake.attributes[aid]["type"] == misp_type
        assert fake.attributes[aid]["to_ids"] is True

    def test_read_back_verification(self) -> None:
        fake = FakeMisp()
        c = client_with(fake)
        aid = c.add_attribute(make_ioc(value="203.0.113.9"))
        assert c.verify_attribute(aid, "203.0.113.9") is True
        assert c.verify_attribute(aid, "9.9.9.9") is False

    def test_missing_attribute_is_not_an_error(self) -> None:
        fake = FakeMisp()
        c = client_with(fake)
        assert c.get_attribute("424242") is None

    def test_delete_confirmed(self) -> None:
        fake = FakeMisp()
        c = client_with(fake)
        aid = c.add_attribute(make_ioc())
        assert c.delete_attribute(aid) is True
        assert c.get_attribute(aid) is None


# -------------------------------------------------------- operations -------
class TestPublishPending:
    def test_unconfigured_reports_skipped(self, db, monkeypatch) -> None:
        monkeypatch.setattr(misp_ops.settings, "misp_url", "")
        monkeypatch.setattr(misp_ops.settings, "misp_key", "")
        out = misp_ops.publish_pending_to_misp(db)
        assert out["status"] == "skipped"
        assert out["published"] == 0

    def test_outage_reports_error_and_audits(self, db, monkeypatch) -> None:
        fake = FakeMisp(fail_auth=True)
        monkeypatch.setattr(misp_ops.settings, "misp_url", "https://misp.lab")
        monkeypatch.setattr(misp_ops.settings, "misp_key", "k" * 32)
        monkeypatch.setattr(misp_ops, "build_client",
                            lambda: MispClient(misp_ops.settings.misp_url,
                                               misp_ops.settings.misp_key,
                                               transport=httpx.MockTransport(fake.handler)))
        out = misp_ops.publish_pending_to_misp(db)
        assert out["status"] == "error"
        audits = db.execute(select(AuditLog).where(AuditLog.success.is_(False))).scalars().all()
        assert audits, "une panne MISP doit etre journalisee en echec"

    def test_happy_path_marks_verified(self, db, monkeypatch) -> None:
        ioc = make_ioc(value="198.51.100.4")
        db.add(ioc)
        db.commit()

        fake = FakeMisp()
        monkeypatch.setattr(misp_ops.settings, "misp_url", "https://misp.lab")
        monkeypatch.setattr(misp_ops.settings, "misp_key", "k" * 32)
        monkeypatch.setattr(misp_ops, "build_client",
                            lambda: MispClient(misp_ops.settings.misp_url,
                                               misp_ops.settings.misp_key,
                                               transport=httpx.MockTransport(fake.handler)))
        out = misp_ops.publish_pending_to_misp(db)
        assert out["status"] == "ok"
        assert out["published"] == 1 and out["verified"] == 1

        pub = db.execute(select(Publication).where(Publication.ioc_id == ioc.id)).scalar_one()
        assert pub.target == "misp"
        assert pub.status == "verified"
        assert pub.target_ref  # MISP attribute id stored

        # idempotent: a second run must not duplicate the publication
        out2 = misp_ops.publish_pending_to_misp(db)
        assert out2["published"] == 0
        assert any(r.get("action") == "already_published" for r in out2["results"])


class TestRevoke:
    def _pub(self, db, ioc) -> Publication:
        pub = Publication(ioc_id=ioc.id, target="misp", target_ref="101",
                          status="verified")
        db.add(pub)
        db.commit()
        return pub

    def test_revocation_requires_remote_confirmation(self, db, monkeypatch) -> None:
        ioc = make_ioc()
        db.add(ioc)
        db.commit()
        pub = self._pub(db, ioc)

        fake = FakeMisp()
        fake.attributes["101"] = {"id": "101", "value": ioc.value}
        monkeypatch.setattr(misp_ops.settings, "misp_url", "https://misp.lab")
        monkeypatch.setattr(misp_ops.settings, "misp_key", "k" * 32)
        monkeypatch.setattr(misp_ops, "build_client",
                            lambda: MispClient(misp_ops.settings.misp_url,
                                               misp_ops.settings.misp_key,
                                               transport=httpx.MockTransport(fake.handler)))
        assert misp_ops.revoke_misp_attribute(db, pub, ioc) is True
        assert pub.revoked_at is not None
        assert pub.status == "revoked"

    def test_unconfirmed_retraction_is_refused(self, db, monkeypatch) -> None:
        """delete says OK but the attribute is STILL there -> not revoked."""
        ioc = make_ioc(value="192.0.2.77")
        db.add(ioc)
        db.commit()
        pub = self._pub(db, ioc)

        fake = FakeMisp(drop_delete=True)     # lies about deletion
        fake.attributes["101"] = {"id": "101", "value": ioc.value}
        monkeypatch.setattr(misp_ops.settings, "misp_url", "https://misp.lab")
        monkeypatch.setattr(misp_ops.settings, "misp_key", "k" * 32)
        monkeypatch.setattr(misp_ops, "build_client",
                            lambda: MispClient(misp_ops.settings.misp_url,
                                               misp_ops.settings.misp_key,
                                               transport=httpx.MockTransport(fake.handler)))
        assert misp_ops.revoke_misp_attribute(db, pub, ioc) is False
        assert pub.revoked_at is None, "la publication doit rester active si non confirmee"
        db.rollback()
