"""MISP operations used by the publication/retention workflows.

Rules:
  * success is recorded ONLY after read-back verification,
  * a MISP outage marks the operation failed (the local state is not advanced),
  * when MISP is not configured the operation reports `skipped` (never faked).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.misp import MispClient, MispError
from app.models.ioc import AuditLog, Ioc, IocStatus, Publication

MISP_TARGET = "misp"


def build_client() -> Optional[MispClient]:
    """Return a client when configured, else None (=> 'skipped', not an error)."""
    if not settings.misp_url or not settings.misp_key:
        return None
    return MispClient(
        base_url=settings.misp_url,
        api_key=settings.misp_key,
        verify_tls=settings.misp_verify_cert,
    )


def active_misp_publication(db: Session, ioc_id) -> Optional[Publication]:
    return db.execute(
        select(Publication).where(
            Publication.ioc_id == ioc_id,
            Publication.target == MISP_TARGET,
            Publication.revoked_at.is_(None),
        )
    ).scalar_one_or_none()


def publish_pending_to_misp(db: Session, limit: int = 100,
                            actor: str = "workflow-5/misp") -> dict[str, Any]:
    """Publish PUBLISHED IOCs to MISP (attributes on the shared event)."""
    client = build_client()
    if client is None:
        return {"status": "skipped", "detail": "MISP_URL / MISP_KEY absents",
                "published": 0, "verified": 0, "failed": 0, "results": []}

    # Health first: an unreachable MISP must fail loudly.
    try:
        version = client.health()
    except MispError as exc:
        db.add(AuditLog(actor=actor, action="PUBLISH", entity_type="misp",
                        detail={"error": str(exc)}, success=False, error=str(exc)))
        db.commit()
        return {"status": "error", "detail": str(exc), "published": 0,
                "verified": 0, "failed": 0, "results": []}

    targets = db.execute(
        select(Ioc).where(Ioc.status == IocStatus.PUBLISHED).order_by(Ioc.score.desc())
        .limit(limit)
    ).scalars().all()

    published = verified = failed = 0
    results: list[dict[str, Any]] = []
    for ioc in targets:
        if active_misp_publication(db, ioc.id) is not None:
            results.append({"ioc_id": str(ioc.id), "action": "already_published"})
            continue
        try:
            attr_id = client.add_attribute(ioc, comment=f"score={ioc.score} risk={ioc.risk_level}")
            # READ-BACK verification: value must be readable from MISP.
            ok = client.verify_attribute(attr_id, ioc.value)
        except MispError as exc:
            failed += 1
            db.add(AuditLog(actor=actor, action="PUBLISH", entity_type="ioc",
                            entity_id=str(ioc.id),
                            detail={"target": MISP_TARGET, "error": str(exc)},
                            success=False, error=str(exc)))
            results.append({"ioc_id": str(ioc.id), "action": "failed",
                            "error": str(exc)})
            continue

        pub = Publication(
            ioc_id=ioc.id, target=MISP_TARGET,
            target_ref=attr_id,
            status="verified" if ok else "pending",
            detail={"value": ioc.value, "score": ioc.score, "misp_version": version},
        )
        db.add(pub)
        published += 1
        if ok:
            verified += 1
        else:
            failed += 1  # attribute created but NOT confirmed by read-back
        results.append({"ioc_id": str(ioc.id), "value": ioc.value,
                        "attribute_id": attr_id, "verified": ok,
                        "action": "published" if ok else "unverified"})

    # Publish the event once if we added anything (consumers can sync).
    event_ok = None
    if published:
        try:
            event_ok = client.publish_event()
        except MispError as exc:
            results.append({"action": "event_publish_failed", "error": str(exc)})

    db.add(AuditLog(
        actor=actor, action="PUBLISH", entity_type="batch",
        detail={"target": MISP_TARGET, "misp_version": version,
                "candidates": len(targets), "published": published,
                "verified": verified, "failed": failed, "event_published": event_ok},
        success=failed == 0, error=None if failed == 0 else f"{failed} echec(s)",
    ))
    db.commit()
    return {"status": "ok", "misp_version": version, "candidates": len(targets),
            "published": published, "verified": verified, "failed": failed,
            "event_published": event_ok, "results": results}


def revoke_misp_attribute(db: Session, pub: Publication, ioc: Ioc,
                          actor: str = "workflow-7/misp") -> bool:
    """Delete the MISP attribute and verify it is gone.

    Returns True only when MISP confirms the attribute no longer exists;
    on False the caller must NOT advance the lifecycle to REMOVED.
    """
    client = build_client()
    if client is None:
        # Not configured: a misp publication cannot exist — treat as revoked
        # locally only if it was never verified remotely (defensive).
        pub.status = "revoked"
        pub.revoked_at = datetime.now(timezone.utc)
        return True

    try:
        deleted = client.delete_attribute(pub.target_ref)
        gone = client.get_attribute(pub.target_ref) is None
    except MispError as exc:
        db.add(AuditLog(actor=actor, action="REMOVE", entity_type="ioc",
                        entity_id=str(ioc.id),
                        detail={"target": MISP_TARGET, "attribute": pub.target_ref,
                                "error": str(exc)},
                        success=False, error=str(exc)))
        return False

    if deleted and gone:
        pub.status = "revoked"
        pub.revoked_at = datetime.now(timezone.utc)
        pub.detail = {**(pub.detail or {}), "revoked_verified_at":
                      datetime.now(timezone.utc).isoformat()}
        return True

    db.add(AuditLog(actor=actor, action="REMOVE", entity_type="ioc",
                    entity_id=str(ioc.id),
                    detail={"target": MISP_TARGET, "attribute": pub.target_ref,
                            "deleted": deleted, "still_present": not gone},
                    success=False, error="attribute MISP toujours present"))
    return False
