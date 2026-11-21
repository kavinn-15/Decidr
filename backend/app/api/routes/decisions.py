from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from app.db.session import get_db
from app.models.models import Decision, DecisionVersion, Premise, Task, Link, AuditLog
from app.models.enums import DecisionStatus
from app.services.ledger import search
from app.services.links import neighbors

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("")
def list_decisions(
    project: Optional[str] = Query(None, description="Filter by project name"),
    status: Optional[str] = Query(None, description="Filter by decision status (active, superseded, at_risk)"),
    text: Optional[str] = Query(None, description="Search term for BM25 ranking"),
    region: Optional[str] = Query(None, description="Filter by region"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    List decisions with optional project, status, region, and BM25 text search.
    Scope filter is applied first, followed by BM25 ranking over decision and premise text.
    """
    scope = {"region": region} if region else None
    dec_status = None
    if status:
        try:
            dec_status = DecisionStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid decision status: {status}")

    scored_hits = search(
        db=db,
        project=project,
        text=text,
        scope=scope,
        status=dec_status,
        limit=limit,
    )

    results = []
    for hit in scored_hits:
        d: Decision = hit["decision"]
        results.append({
            "id": d.id,
            "item_id": d.item_id,
            "text": d.text,
            "scope_project": d.scope_project,
            "scope_region": d.scope_region,
            "scope_release": d.scope_release,
            "effective_from": d.effective_from.isoformat() if d.effective_from else None,
            "effective_to": d.effective_to.isoformat() if d.effective_to else None,
            "status": d.status.value,
            "version": d.version,
            "supersedes_id": d.supersedes_id,
            "score": round(hit["score"], 4),
            "premises_count": len(d.premises),
            "premises": [
                {
                    "id": p.id,
                    "text": p.text,
                    "evidence_quote": p.evidence_quote,
                    "state": p.state.value,
                    "status": p.status.value,
                    "valid_from": p.valid_from.isoformat() if p.valid_from else None,
                    "valid_until": p.valid_until.isoformat() if p.valid_until else None,
                }
                for p in d.premises
            ],
        })

    return results


@router.get("/{id}")
def get_decision_detail(
    id: int,
    db: Session = Depends(get_db),
):
    """
    Returns full decision details:
    - decision core info
    - premises with status and state
    - linked tasks (both direct task.decision_id and confirmed graph links)
    - version history from decision_versions
    - status timeline from audit_log
    """
    decision = (
        db.query(Decision)
        .options(
            selectinload(Decision.premises),
            selectinload(Decision.versions),
            selectinload(Decision.tasks),
        )
        .filter(Decision.id == id)
        .first()
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # 1. Premises with status
    premises_data = [
        {
            "id": p.id,
            "text": p.text,
            "evidence_quote": p.evidence_quote,
            "utterance_id": p.utterance_id,
            "scope_project": p.scope_project,
            "scope_region": p.scope_region,
            "valid_from": p.valid_from.isoformat() if p.valid_from else None,
            "valid_until": p.valid_until.isoformat() if p.valid_until else None,
            "state": p.state.value,
            "status": p.status.value,
            "confirmed_by": p.confirmed_by,
        }
        for p in decision.premises
    ]

    # 2. Linked tasks (direct task.decision_id + confirmed graph neighbors)
    task_map: Dict[int, Task] = {}
    for t in decision.tasks:
        task_map[t.id] = t

    # Invariant 4: Graph queries must ignore unconfirmed links by default (confirmed_only=True)
    graph_neighbors = neighbors(db, ("decision", decision.id), confirmed_only=True)
    for n in graph_neighbors:
        if n["node_type"] == "task" and n["node_id"] not in task_map:
            t_obj = db.get(Task, n["node_id"])
            if t_obj:
                task_map[t_obj.id] = t_obj

    tasks_data = [
        {
            "id": t.id,
            "item_id": t.item_id,
            "title": t.title,
            "description": t.description,
            "owner_id": t.owner_id,
            "owner_name": t.owner.name if t.owner else None,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "estimate_hours": t.estimate_hours,
            "provisional": t.provisional,
            "status": t.status.value,
            "tracker_ref": t.tracker_ref,
            "tracker_url": t.tracker_url,
        }
        for t in task_map.values()
    ]

    # 3. Version history
    versions_data = [
        {
            "id": v.id,
            "version": v.version,
            "text": v.text,
            "changed_at": v.changed_at.isoformat() if v.changed_at else None,
            "changed_by": v.changed_by,
        }
        for v in sorted(decision.versions, key=lambda x: x.version)
    ]

    # 4. Status timeline from audit_log
    audit_entries = (
        db.query(AuditLog)
        .filter(
            or_(
                (AuditLog.entity_type == "decision") & (AuditLog.entity_id == decision.id),
                (AuditLog.entity_type == "decision_version") & (AuditLog.entity_id == decision.id),
            )
        )
        .order_by(AuditLog.id.asc())
        .all()
    )

    status_timeline = [
        {
            "id": entry.id,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "actor": entry.actor,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "before": entry.before,
            "after": entry.after,
        }
        for entry in audit_entries
    ]

    return {
        "decision": {
            "id": decision.id,
            "item_id": decision.item_id,
            "text": decision.text,
            "scope_project": decision.scope_project,
            "scope_region": decision.scope_region,
            "scope_release": decision.scope_release,
            "effective_from": decision.effective_from.isoformat() if decision.effective_from else None,
            "effective_to": decision.effective_to.isoformat() if decision.effective_to else None,
            "status": decision.status.value,
            "version": decision.version,
            "supersedes_id": decision.supersedes_id,
            "embedding": decision.embedding,
        },
        "premises": premises_data,
        "linked_tasks": tasks_data,
        "version_history": versions_data,
        "status_timeline": status_timeline,
    }
