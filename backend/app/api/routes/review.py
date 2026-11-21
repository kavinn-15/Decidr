from datetime import date, datetime, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import (
    ReviewState,
    DecisionStatus,
    PremiseState,
    PremiseStatus,
    TaskStatus,
    AlertState,
    ProposalState,
    ActionType,
    ActionState,
    ItemType,
)
from app.models.models import (
    Meeting,
    Item,
    Decision,
    DecisionVersion,
    Premise,
    Task,
    Link,
    Alert,
    ChangeProposal,
    ChangeAction,
    Person,
)
from app.services.audit import log
from app.services.executor import execute_proposal

router = APIRouter(tags=["review"])


# --- Request Schemas ---

class EditDecisionRequest(BaseModel):
    actor: str = "reviewer"
    text: Optional[str] = None
    scope_project: Optional[str] = None
    scope_region: Optional[str] = None
    scope_release: Optional[str] = None


class EditPremiseRequest(BaseModel):
    actor: str = "reviewer"
    text: Optional[str] = None
    valid_until: Optional[date] = None


class ApproveActionRequest(BaseModel):
    actor: str = "reviewer"
    owner_id: Optional[int] = None
    deadline: Optional[date] = None
    estimate_hours: Optional[float] = None
    approve_unassigned: bool = False


class EditActionRequest(BaseModel):
    actor: str = "reviewer"
    text: Optional[str] = None
    owner_id: Optional[int] = None
    deadline: Optional[date] = None
    estimate_hours: Optional[float] = None


class GenericActionRequest(BaseModel):
    actor: str = "reviewer"


# --- Review Queue GET Endpoint ---

@router.get("/meetings/{meeting_id}/review")
def get_meeting_review_queue(meeting_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Returns review queue cards in strict priority order:
    1. Premise break and conflict alerts first
    2. Decisions, each with nested premise cards
    3. Action items (with owner, deadline, and provisional status)
    4. Low-confidence link confirmation cards
    """
    meeting = db.query(Meeting).filter_by(id=meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting with id {meeting_id} not found",
        )

    # 1. Alerts for this meeting (premise_break, conflict, expiry)
    alerts = (
        db.query(Alert)
        .filter(Alert.meeting_id == meeting_id)
        .order_by(Alert.id.asc())
        .all()
    )
    alerts_data = []
    for a in alerts:
        alerts_data.append({
            "id": a.id,
            "kind": a.kind.value,
            "verdict": a.verdict,
            "old_quote": a.old_quote,
            "new_quote": a.new_quote,
            "explanation": a.explanation,
            "state": a.state.value,
            "decision_id": a.decision_id,
            "premise_id": a.premise_id,
            "utterance_id": a.utterance_id,
            "utterance_idx": a.utterance.idx if a.utterance else None,
        })

    # 2. Decisions with nested Premises
    decision_items = (
        db.query(Item)
        .filter(Item.meeting_id == meeting_id, Item.type == ItemType.decision)
        .order_by(Item.id.asc())
        .all()
    )
    decisions_data = []
    for d_item in decision_items:
        decision = d_item.decision
        premises_data = []
        if decision:
            for p in decision.premises:
                premises_data.append({
                    "id": p.id,
                    "decision_id": p.decision_id,
                    "text": p.text,
                    "evidence_quote": p.evidence_quote,
                    "utterance_id": p.utterance_id,
                    "utterance_idx": p.utterance.idx if p.utterance else None,
                    "speaker": p.utterance.speaker_raw if p.utterance else None,
                    "valid_until": p.valid_until.isoformat() if p.valid_until else None,
                    "state": p.state.value,
                    "status": p.status.value,
                    "confirmed_by": p.confirmed_by,
                })

        decisions_data.append({
            "item_id": d_item.id,
            "decision_id": decision.id if decision else None,
            "text": decision.text if decision else d_item.text,
            "confidence": d_item.confidence,
            "evidence_quote": d_item.evidence_quote,
            "utterance_id": d_item.utterance_id,
            "utterance_idx": d_item.utterance.idx if d_item.utterance else None,
            "speaker": d_item.utterance.speaker_raw if d_item.utterance else None,
            "scope_project": decision.scope_project if decision else meeting.project,
            "scope_region": decision.scope_region if decision else meeting.region,
            "scope_release": decision.scope_release if decision else meeting.release,
            "version": decision.version if decision else 1,
            "status": decision.status.value if decision else DecisionStatus.active.value,
            "review_state": d_item.review_state.value,
            "premises": premises_data,
        })

    # 3. Action items
    action_items = (
        db.query(Item)
        .filter(Item.meeting_id == meeting_id, Item.type == ItemType.action)
        .order_by(Item.id.asc())
        .all()
    )
    actions_data = []
    for a_item in action_items:
        task = a_item.task
        linked_decision = None
        if task and task.decision:
            linked_decision = {
                "id": task.decision.id,
                "text": task.decision.text,
                "scope_region": task.decision.scope_region,
            }

        actions_data.append({
            "item_id": a_item.id,
            "task_id": task.id if task else None,
            "text": a_item.text,
            "confidence": a_item.confidence,
            "evidence_quote": a_item.evidence_quote,
            "utterance_id": a_item.utterance_id,
            "utterance_idx": a_item.utterance.idx if a_item.utterance else None,
            "speaker": a_item.utterance.speaker_raw if a_item.utterance else None,
            "owner_id": a_item.owner_id,
            "owner_name": a_item.owner.name if a_item.owner else None,
            "deadline": a_item.deadline.isoformat() if a_item.deadline else None,
            "needs_owner": a_item.needs_owner,
            "needs_deadline": a_item.needs_deadline,
            "estimate_hours": task.estimate_hours if task else None,
            "provisional": task.provisional if task else True,
            "review_state": a_item.review_state.value,
            "tracker_ref": task.tracker_ref if task else None,
            "tracker_url": task.tracker_url if task else None,
            "linked_decision": linked_decision,
        })

    # 4. Low-confidence Link confirmation cards
    # Links where confirmed=False or confidence < 0.8 associated with tasks in this meeting
    task_ids = [a["task_id"] for a in actions_data if a["task_id"] is not None]
    links = []
    if task_ids:
        links = (
            db.query(Link)
            .filter(
                Link.source_type == "task",
                Link.source_id.in_(task_ids),
            )
            .all()
        )
    links_data = []
    for lnk in links:
        task_obj = db.get(Task, lnk.source_id)
        decision_obj = db.get(Decision, lnk.target_id)
        links_data.append({
            "id": lnk.id,
            "source_type": lnk.source_type,
            "source_id": lnk.source_id,
            "source_title": task_obj.title if task_obj else f"Task #{lnk.source_id}",
            "target_type": lnk.target_type,
            "target_id": lnk.target_id,
            "target_title": decision_obj.text if decision_obj else f"Decision #{lnk.target_id}",
            "relation": lnk.relation.value,
            "confidence": lnk.confidence,
            "confirmed": lnk.confirmed,
            "rationale": lnk.rationale,
        })

    # 5. Roster people for easy assignment in UI
    people = db.query(Person).order_by(Person.name.asc()).all()
    people_data = [
        {"id": p.id, "name": p.name, "email": p.email, "tracker_id": p.tracker_id}
        for p in people
    ]

    return {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "date": meeting.date.isoformat(),
        "project": meeting.project,
        "region": meeting.region,
        "release": meeting.release,
        "status": meeting.status.value,
        "alerts": alerts_data,
        "decisions": decisions_data,
        "actions": actions_data,
        "links": links_data,
        "people": people_data,
    }


# --- Decision Review Endpoints ---

@router.post("/review/decisions/{item_id}/approve")
def approve_decision(
    item_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    """
    Approving a decision creates the decisions row plus a decision_versions row.
    Writes an append-only audit log row.
    """
    item = db.get(Item, item_id)
    if not item or item.type != ItemType.decision:
        raise HTTPException(status_code=404, detail="Decision item not found")

    actor = payload.actor
    prev_state = item.review_state.value
    item.review_state = ReviewState.approved

    # Create or update Decision row
    decision = item.decision
    if not decision:
        decision = Decision(
            item_id=item.id,
            text=item.text,
            scope_project=item.meeting.project,
            scope_region=item.meeting.region,
            scope_release=item.meeting.release,
            effective_from=item.meeting.date,
            status=DecisionStatus.active,
            version=1,
        )
        db.add(decision)
        db.flush()
    else:
        decision.status = DecisionStatus.active

    # Create decision_versions row if version 1 not present
    existing_version = (
        db.query(DecisionVersion)
        .filter_by(decision_id=decision.id, version=decision.version)
        .first()
    )
    if not existing_version:
        v_entry = DecisionVersion(
            decision_id=decision.id,
            version=decision.version,
            text=decision.text,
            changed_at=datetime.now(timezone.utc),
            changed_by=actor,
        )
        db.add(v_entry)
        db.flush()

    log(
        actor=actor,
        action="approve_decision",
        entity_type="item",
        entity_id=item.id,
        before={"review_state": prev_state},
        after={"review_state": item.review_state.value, "decision_id": decision.id},
        db=db,
    )
    db.commit()

    # Detect conflicts / supersession against earlier active decisions
    from app.services.conflicts import detect_conflicts_for_decision
    try:
        detect_conflicts_for_decision(db, decision, actor=actor)
        db.commit()
    except Exception as e:
        logger.warning(f"Error checking decision conflicts upon approval: {e}")

    return {
        "status": "approved",
        "item_id": item.id,
        "decision_id": decision.id,
        "version": decision.version,
    }


@router.post("/review/decisions/{item_id}/reject")
def reject_decision(
    item_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)
    if not item or item.type != ItemType.decision:
        raise HTTPException(status_code=404, detail="Decision item not found")

    prev_state = item.review_state.value
    item.review_state = ReviewState.rejected

    log(
        actor=payload.actor,
        action="reject_decision",
        entity_type="item",
        entity_id=item.id,
        before={"review_state": prev_state},
        after={"review_state": item.review_state.value},
        db=db,
    )
    db.commit()
    return {"status": "rejected", "item_id": item.id}


@router.post("/review/decisions/{item_id}/edit")
def edit_decision(
    item_id: int,
    payload: EditDecisionRequest,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)
    if not item or item.type != ItemType.decision:
        raise HTTPException(status_code=404, detail="Decision item not found")

    before = {"text": item.text}
    if payload.text:
        item.text = payload.text
    item.review_state = ReviewState.edited

    decision = item.decision
    if decision:
        before.update({
            "scope_project": decision.scope_project,
            "scope_region": decision.scope_region,
            "version": decision.version,
        })
        if payload.text:
            decision.text = payload.text
        if payload.scope_project:
            decision.scope_project = payload.scope_project
        if payload.scope_region is not None:
            decision.scope_region = payload.scope_region
        if payload.scope_release is not None:
            decision.scope_release = payload.scope_release

        decision.version += 1
        v_entry = DecisionVersion(
            decision_id=decision.id,
            version=decision.version,
            text=decision.text,
            changed_at=datetime.now(timezone.utc),
            changed_by=payload.actor,
        )
        db.add(v_entry)

    log(
        actor=payload.actor,
        action="edit_decision",
        entity_type="item",
        entity_id=item.id,
        before=before,
        after={"text": item.text, "version": decision.version if decision else 1},
        db=db,
    )
    db.commit()

    return {
        "status": "edited",
        "item_id": item.id,
        "decision_id": decision.id if decision else None,
        "text": item.text,
        "version": decision.version if decision else 1,
    }


# --- Premise Review Endpoints ---

@router.post("/review/premises/{premise_id}/approve")
def approve_premise(
    premise_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    """
    Approving a premise sets state=confirmed and status=holding.
    """
    premise = db.get(Premise, premise_id)
    if not premise:
        raise HTTPException(status_code=404, detail="Premise not found")

    before = {
        "state": premise.state.value,
        "status": premise.status.value,
        "confirmed_by": premise.confirmed_by,
    }
    premise.state = PremiseState.confirmed
    premise.status = PremiseStatus.holding
    premise.confirmed_by = payload.actor

    log(
        actor=payload.actor,
        action="approve_premise",
        entity_type="premise",
        entity_id=premise.id,
        before=before,
        after={
            "state": premise.state.value,
            "status": premise.status.value,
            "confirmed_by": premise.confirmed_by,
        },
        db=db,
    )
    db.commit()
    return {"status": "confirmed", "premise_id": premise.id}


@router.post("/review/premises/{premise_id}/reject")
def reject_premise(
    premise_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    """
    Rejecting a premise means it is never used.
    """
    premise = db.get(Premise, premise_id)
    if not premise:
        raise HTTPException(status_code=404, detail="Premise not found")

    before = {"state": premise.state.value}
    premise.state = PremiseState.rejected

    log(
        actor=payload.actor,
        action="reject_premise",
        entity_type="premise",
        entity_id=premise.id,
        before=before,
        after={"state": premise.state.value},
        db=db,
    )
    db.commit()
    return {"status": "rejected", "premise_id": premise.id}


@router.post("/review/premises/{premise_id}/edit")
def edit_premise(
    premise_id: int,
    payload: EditPremiseRequest,
    db: Session = Depends(get_db),
):
    premise = db.get(Premise, premise_id)
    if not premise:
        raise HTTPException(status_code=404, detail="Premise not found")

    before = {
        "text": premise.text,
        "valid_until": premise.valid_until.isoformat() if premise.valid_until else None,
    }
    if payload.text:
        premise.text = payload.text
    if payload.valid_until is not None:
        premise.valid_until = payload.valid_until

    log(
        actor=payload.actor,
        action="edit_premise",
        entity_type="premise",
        entity_id=premise.id,
        before=before,
        after={
            "text": premise.text,
            "valid_until": premise.valid_until.isoformat() if premise.valid_until else None,
        },
        db=db,
    )
    db.commit()
    return {"status": "edited", "premise_id": premise.id, "text": premise.text}


# --- Action Review Endpoints ---

@router.post("/review/actions/{item_id}/approve")
def approve_action(
    item_id: int,
    payload: ApproveActionRequest,
    db: Session = Depends(get_db),
):
    """
    Approving an action:
    - Missing owner/deadline rule: can be approved only after reviewer fills the field
      or explicitly chooses 'approve_unassigned'.
    - If any premise of the linked decision is unconfirmed, task is created with
      provisional=true and the ticket gets label and 'Rests on an unverified premise'.
    - Creates task and approved create_task change_action, then runs executor
      so a real ticket appears.
    - Writes append-only audit log row.
    """
    item = db.get(Item, item_id)
    if not item or item.type != ItemType.action:
        raise HTTPException(status_code=404, detail="Action item not found")

    task = item.task
    if not task:
        task = Task(
            item_id=item.id,
            title=item.text,
            owner_id=item.owner_id,
            due_date=item.deadline,
            provisional=True,
            status=TaskStatus.open,
        )
        db.add(task)
        db.flush()

    # Update owner/deadline if provided in request
    if payload.owner_id is not None:
        item.owner_id = payload.owner_id
        task.owner_id = payload.owner_id
        item.needs_owner = False
    if payload.deadline is not None:
        item.deadline = payload.deadline
        task.due_date = payload.deadline
        item.needs_deadline = False
    if payload.estimate_hours is not None:
        task.estimate_hours = payload.estimate_hours

    # Missing owner or deadline validation rule (Invariant 1)
    if (item.owner_id is None or item.deadline is None) and not payload.approve_unassigned:
        missing_fields = []
        if item.owner_id is None:
            missing_fields.append("owner")
        if item.deadline is None:
            missing_fields.append("deadline")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Action requires {' and '.join(missing_fields)}. "
                f"Please assign the fields or explicitly choose 'Approve Unassigned'."
            ),
        )

    prev_state = item.review_state.value
    item.review_state = ReviewState.approved

    # Check linked decision premises for provisional rule (Invariant 4)
    # "If any premise of the linked decision is unconfirmed, the task is created with provisional=true
    #  and the ticket gets a visible label and a line 'Rests on an unverified premise'."
    is_provisional = False
    extra_notice = ""
    labels = ["decidr"]

    if task.decision_id:
        decision_premises = (
            db.query(Premise)
            .filter(Premise.decision_id == task.decision_id)
            .all()
        )
        # If premises exist and any is NOT confirmed:
        if decision_premises and any(p.state != PremiseState.confirmed for p in decision_premises):
            is_provisional = True
        elif not decision_premises:
            # If decision exists but has no confirmed premises, it's unverified
            is_provisional = True
    else:
        # No linked decision -> provisional
        is_provisional = True

    task.provisional = is_provisional
    if is_provisional:
        labels.append("provisional")
        extra_notice = "\n\n> ⚠️ **Notice**: Rests on an unverified premise."

    # Create change_proposal and change_action in state 'approved'
    proposal = ChangeProposal(
        trigger_type="action_approval",
        trigger_id=item.id,
        summary=f"Human approval for task: {item.text}",
        state=ProposalState.approved,
        decided_by=payload.actor,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(proposal)
    db.flush()

    ticket_description = (task.description or item.text) + extra_notice
    assignee = (
        task.owner.tracker_id or task.owner.email
        if task.owner
        else None
    )

    action_payload = {
        "title": item.text,
        "description": ticket_description,
        "assignee": assignee,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "labels": labels,
        "provisional": is_provisional,
    }

    change_action = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload=action_payload,
        idempotency_key=f"action-create-task-{task.id}-{item.id}",
        state=ActionState.approved,
    )
    db.add(change_action)
    db.flush()

    # Run the executor so a real ticket appears
    exec_res = execute_proposal(proposal.id, actor=payload.actor, db=db)

    # Log audit entry
    log(
        actor=payload.actor,
        action="approve_action",
        entity_type="item",
        entity_id=item.id,
        before={"review_state": prev_state},
        after={
            "review_state": item.review_state.value,
            "task_id": task.id,
            "provisional": task.provisional,
            "tracker_ref": task.tracker_ref,
        },
        db=db,
    )
    db.commit()
    db.refresh(task)

    return {
        "status": "approved",
        "item_id": item.id,
        "task_id": task.id,
        "provisional": task.provisional,
        "tracker_ref": task.tracker_ref,
        "tracker_url": task.tracker_url,
        "executor_result": exec_res,
    }


@router.post("/review/actions/{item_id}/reject")
def reject_action(
    item_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    """
    Rejecting an action calls nothing on the external tracker.
    """
    item = db.get(Item, item_id)
    if not item or item.type != ItemType.action:
        raise HTTPException(status_code=404, detail="Action item not found")

    prev_state = item.review_state.value
    item.review_state = ReviewState.rejected

    if item.task:
        item.task.status = TaskStatus.cancelled

    log(
        actor=payload.actor,
        action="reject_action",
        entity_type="item",
        entity_id=item.id,
        before={"review_state": prev_state},
        after={"review_state": item.review_state.value},
        db=db,
    )
    db.commit()
    return {"status": "rejected", "item_id": item.id}


@router.post("/review/actions/{item_id}/edit")
def edit_action(
    item_id: int,
    payload: EditActionRequest,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)
    if not item or item.type != ItemType.action:
        raise HTTPException(status_code=404, detail="Action item not found")

    task = item.task
    before = {
        "text": item.text,
        "owner_id": item.owner_id,
        "deadline": item.deadline.isoformat() if item.deadline else None,
    }

    if payload.text:
        item.text = payload.text
        if task:
            task.title = payload.text

    if payload.owner_id is not None:
        item.owner_id = payload.owner_id
        item.needs_owner = False
        if task:
            task.owner_id = payload.owner_id

    if payload.deadline is not None:
        item.deadline = payload.deadline
        item.needs_deadline = False
        if task:
            task.due_date = payload.deadline

    if payload.estimate_hours is not None and task:
        task.estimate_hours = payload.estimate_hours

    item.review_state = ReviewState.edited

    log(
        actor=payload.actor,
        action="edit_action",
        entity_type="item",
        entity_id=item.id,
        before=before,
        after={
            "text": item.text,
            "owner_id": item.owner_id,
            "deadline": item.deadline.isoformat() if item.deadline else None,
        },
        db=db,
    )
    db.commit()

    return {
        "status": "edited",
        "item_id": item.id,
        "task_id": task.id if task else None,
        "text": item.text,
        "owner_id": item.owner_id,
        "deadline": item.deadline.isoformat() if item.deadline else None,
    }


# --- Link Review Endpoints ---

@router.post("/review/links/{link_id}/confirm")
def confirm_link(
    link_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    before = {"confirmed": link.confirmed}
    link.confirmed = True

    log(
        actor=payload.actor,
        action="confirm_link",
        entity_type="link",
        entity_id=link.id,
        before=before,
        after={"confirmed": link.confirmed},
        db=db,
    )
    db.commit()
    return {"status": "confirmed", "link_id": link.id}


@router.post("/review/links/{link_id}/reject")
def reject_link(
    link_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    before = {"confirmed": link.confirmed}
    link.confirmed = False

    log(
        actor=payload.actor,
        action="reject_link",
        entity_type="link",
        entity_id=link.id,
        before=before,
        after={"confirmed": link.confirmed},
        db=db,
    )
    db.commit()
    return {"status": "rejected", "link_id": link.id}


# --- Alert Review Endpoints ---

@router.post("/review/alerts/{alert_id}/confirm")
def confirm_alert(
    alert_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # If it is a supersedes alert, run the full supersedes workflow
    if alert.verdict and "supersedes" in alert.verdict.lower():
        from app.services.conflicts import approve_supersedes_alert
        try:
            confirmed_alert = approve_supersedes_alert(db, alert_id, actor=payload.actor)
            db.commit()
            return {"status": "confirmed", "alert_id": confirmed_alert.id, "verdict": confirmed_alert.verdict}
        except Exception as e:
            logger.warning(f"Failed to execute supersedes approval workflow: {e}")

    before = {"state": alert.state.value}
    alert.state = AlertState.confirmed

    log(
        actor=payload.actor,
        action="confirm_alert",
        entity_type="alert",
        entity_id=alert.id,
        before=before,
        after={"state": alert.state.value},
        db=db,
    )
    db.commit()
    return {"status": "confirmed", "alert_id": alert.id}


@router.post("/review/alerts/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: int,
    payload: GenericActionRequest = GenericActionRequest(),
    db: Session = Depends(get_db),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    before = {"state": alert.state.value}
    alert.state = AlertState.dismissed

    log(
        actor=payload.actor,
        action="dismiss_alert",
        entity_type="alert",
        entity_id=alert.id,
        before=before,
        after={"state": alert.state.value},
        db=db,
    )
    db.commit()
    return {"status": "dismissed", "alert_id": alert.id}
