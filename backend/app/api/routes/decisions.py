from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from app.db.session import get_db
from app.models.models import Decision, DecisionVersion, Premise, Task, Link, AuditLog, User
from app.models.enums import DecisionStatus
from app.services.ledger import search
from app.services.links import neighbors
from app.api.deps import get_current_user, verify_project_access

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("")
def list_decisions(
    project: Optional[str] = Query(None, description="Filter by project name"),
    status: Optional[str] = Query(None, description="Filter by decision status (active, superseded, at_risk)"),
    text: Optional[str] = Query(None, description="Search term for BM25 ranking"),
    region: Optional[str] = Query(None, description="Filter by region"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List decisions with optional project, status, region, and BM25 text search.
    Scope filter is applied first, followed by BM25 ranking over decision and premise text.
    """
    if project:
        verify_project_access(project, current_user, db)
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
    current_user: User = Depends(get_current_user),
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
            selectinload(Decision.premises).selectinload(Premise.utterance),
            selectinload(Decision.versions),
            selectinload(Decision.tasks),
            selectinload(Decision.item),
        )
        .filter(Decision.id == id)
        .first()
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    verify_project_access(decision.scope_project, current_user, db)

    meeting = decision.item.meeting if (decision.item and decision.item.meeting) else None

    # 1. Premises with status
    premises_data = []
    for p in decision.premises:
        p_meeting = p.utterance.meeting if (p.utterance and p.utterance.meeting) else meeting
        premises_data.append({
            "id": p.id,
            "text": p.text,
            "evidence_quote": p.evidence_quote,
            "utterance_id": p.utterance_id,
            "utterance_idx": p.utterance.idx if p.utterance else None,
            "speaker_name": p.utterance.speaker_name if p.utterance else None,
            "utterance_text": p.utterance.text if p.utterance else None,
            "meeting_id": p_meeting.id if p_meeting else None,
            "meeting_title": p_meeting.title if p_meeting else None,
            "meeting_date": p_meeting.date.isoformat() if (p_meeting and p_meeting.date) else None,
            "scope_project": p.scope_project,
            "scope_region": p.scope_region,
            "valid_from": p.valid_from.isoformat() if p.valid_from else None,
            "valid_until": p.valid_until.isoformat() if p.valid_until else None,
            "state": p.state.value,
            "status": p.status.value,
            "confirmed_by": p.confirmed_by,
        })

    # 2. Linked tasks (direct task.decision_id + graph links)
    task_map: Dict[int, Task] = {}
    for t in decision.tasks:
        task_map[t.id] = t

    # Find link rows connecting tasks to this decision
    links = (
        db.query(Link)
        .filter(
            Link.target_type == "decision",
            Link.target_id == decision.id,
            Link.source_type == "task",
        )
        .all()
    )
    link_confirmations = {l.source_id: l.confirmed for l in links}

    # Also include tasks linked via Link table
    for l in links:
        if l.source_id not in task_map:
            t_obj = db.get(Task, l.source_id)
            if t_obj:
                task_map[t_obj.id] = t_obj

    tasks_data = []
    for t in task_map.values():
        is_confirmed = link_confirmations.get(t.id, not t.provisional)
        tasks_data.append({
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
            "link_confirmed": is_confirmed,
        })

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

    # 4. Status timeline from audit_log with human-readable causes
    audit_entries = (
        db.query(AuditLog)
        .filter(
            or_(
                (AuditLog.entity_type == "decision") & (AuditLog.entity_id == decision.id),
                (AuditLog.entity_type == "decision_version") & (AuditLog.entity_id == decision.id),
                (AuditLog.entity_type == "item") & (AuditLog.entity_id == decision.item_id),
            )
        )
        .order_by(AuditLog.id.asc())
        .all()
    )

    status_timeline = []
    has_creation_log = any(
        e.action in ("approve_decision", "create_decision", "create_item") for e in audit_entries
    )
    if not has_creation_log:
        if decision.effective_from:
            if isinstance(decision.effective_from, datetime):
                created_iso = decision.effective_from.isoformat()
            elif isinstance(decision.effective_from, date):
                created_iso = datetime.combine(decision.effective_from, datetime.min.time(), tzinfo=timezone.utc).isoformat()
            else:
                created_iso = str(decision.effective_from)
        else:
            created_iso = datetime.now(timezone.utc).isoformat()

        status_timeline.append({
            "id": 0,
            "created_at": created_iso,
            "actor": "reviewer",
            "action": "approve_decision",
            "status": "active",
            "cause": "Approved during meeting review (Initial decision adoption)",
            "before": None,
            "after": {"status": "active", "version": 1},
        })

    for entry in audit_entries:
        cause = None
        status_val = None
        if entry.after and isinstance(entry.after, dict):
            status_val = entry.after.get("status") or entry.after.get("review_state")
            cause = entry.after.get("cause") or entry.after.get("reason")

        if not cause:
            if "approve_decision" in entry.action or "approve" in entry.action:
                cause = "Approved during meeting review"
                status_val = status_val or "active"
            elif "mark_decision_at_risk" in entry.action or "at_risk" in entry.action:
                cause = "Underlying premise broken; repair action marked decision at risk"
                status_val = status_val or "at_risk"
            elif "supersede" in entry.action:
                cause = "Superseded by a newer conflicting decision"
                status_val = status_val or "superseded"
            elif "edit" in entry.action:
                cause = "Decision text or scope updated"
            else:
                cause = f"Action: {entry.action}"

        status_timeline.append({
            "id": entry.id,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "actor": entry.actor,
            "action": entry.action,
            "status": status_val or decision.status.value,
            "cause": cause,
            "before": entry.before,
            "after": entry.after,
        })

    # If current status is at_risk or superseded but not recorded in timeline, append current state
    has_current_status = any(e.get("status") == decision.status.value for e in status_timeline)
    if not has_current_status and decision.status != DecisionStatus.active:
        cause = (
            "Marked at risk due to premise break"
            if decision.status == DecisionStatus.at_risk
            else "Superseded by newer decision"
        )
        status_timeline.append({
            "id": 999999,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "actor": "system",
            "action": f"mark_{decision.status.value}",
            "status": decision.status.value,
            "cause": cause,
            "before": {"status": "active"},
            "after": {"status": decision.status.value},
        })

    return {
        "decision": {
            "id": decision.id,
            "item_id": decision.item_id,
            "meeting_id": meeting.id if meeting else None,
            "meeting_title": meeting.title if meeting else None,
            "meeting_date": meeting.date.isoformat() if (meeting and meeting.date) else None,
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
