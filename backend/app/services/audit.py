from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.models import AuditLog


def log(
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> AuditLog:
    """
    Append an entry to the audit log.
    Every state change in Decidr writes an audit_log row (Invariant 7).
    """
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        created_at=datetime.now(timezone.utc),
    )

    if db is not None:
        db.add(entry)
        db.flush()
        return entry

    with SessionLocal() as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
