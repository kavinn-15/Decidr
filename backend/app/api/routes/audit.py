import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import AuditLog, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogItemRead(BaseModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: int
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    created_at: datetime


class AuditListResponse(BaseModel):
    total: int
    items: List[AuditLogItemRead]


class AuditFiltersResponse(BaseModel):
    actors: List[str]
    actions: List[str]
    entity_types: List[str]


@router.get("", response_model=AuditListResponse)
def get_audit_logs(
    actor: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns newest-first audit log entries with filtering for actor, action, and entity type.
    Audit log is strictly read-only and append-only (Invariant 7).
    """
    query = db.query(AuditLog)

    if actor and actor.strip():
        query = query.filter(AuditLog.actor == actor.strip())
    if action and action.strip():
        query = query.filter(AuditLog.action == action.strip())
    if entity_type and entity_type.strip():
        query = query.filter(AuditLog.entity_type == entity_type.strip())

    total = query.count()
    items = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()

    return AuditListResponse(
        total=total,
        items=[
            AuditLogItemRead(
                id=a.id,
                actor=a.actor,
                action=a.action,
                entity_type=a.entity_type,
                entity_id=a.entity_id,
                before=a.before,
                after=a.after,
                created_at=a.created_at,
            )
            for a in items
        ],
    )


@router.get("/filters", response_model=AuditFiltersResponse)
def get_audit_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns distinct values for actors, actions, and entity types in the audit log.
    """
    actors = [r[0] for r in db.query(AuditLog.actor).distinct().order_by(AuditLog.actor).all() if r[0]]
    actions = [r[0] for r in db.query(AuditLog.action).distinct().order_by(AuditLog.action).all() if r[0]]
    entity_types = [
        r[0] for r in db.query(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type).all() if r[0]
    ]

    return AuditFiltersResponse(
        actors=actors,
        actions=actions,
        entity_types=entity_types,
    )


@router.get("/export")
def export_audit_logs_csv(
    actor: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Exports filtered audit logs as a downloadable CSV file.
    """
    query = db.query(AuditLog)

    if actor and actor.strip():
        query = query.filter(AuditLog.actor == actor.strip())
    if action and action.strip():
        query = query.filter(AuditLog.action == action.strip())
    if entity_type and entity_type.strip():
        query = query.filter(AuditLog.entity_type == entity_type.strip())

    items = query.order_by(AuditLog.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Actor", "Action", "Entity Type", "Entity ID", "Before", "After"])

    for a in items:
        writer.writerow([
            a.id,
            a.created_at.isoformat() if a.created_at else "",
            a.actor,
            a.action,
            a.entity_type,
            a.entity_id,
            json.dumps(a.before) if a.before else "",
            json.dumps(a.after) if a.after else "",
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=decidr_audit_log.csv"},
    )
