from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import ChangeProposal, ChangeAction, Task, Decision, User
from app.models.enums import ProposalState, ActionState, ActionType
from app.services.executor import _build_action_payload, execute_proposal, ProposalNotApprovedError
from app.services.audit import log
from app.api.deps import get_current_user, verify_project_access

router = APIRouter(prefix="/proposals", tags=["proposals"])


class ActionEditItem(BaseModel):
    action_id: int
    edited_payload: Optional[Dict[str, Any]] = None


class ApproveProposalRequest(BaseModel):
    actor: str = "reviewer"
    action_ids: Optional[List[int]] = None
    edited_payloads: Optional[Dict[int, Dict[str, Any]]] = None
    actions: Optional[List[ActionEditItem]] = None


class RejectProposalRequest(BaseModel):
    actor: str = "reviewer"


class PreviewProposalRequest(BaseModel):
    action_ids: Optional[List[int]] = None
    edited_payloads: Optional[Dict[int, Dict[str, Any]]] = None


@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns proposal metadata and every action with its target and the exact payload that will be sent.
    """
    proposal = db.get(ChangeProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal #{proposal_id} not found")

    alert = proposal.alerts[0] if proposal.alerts else None
    if alert and alert.meeting:
        verify_project_access(alert.meeting.project, current_user, db)

    actions_data = []
    for action in proposal.actions:
        target_name = None
        if action.target_type == "task":
            t = db.get(Task, action.target_id)
            if t:
                target_name = f"T{t.id}: {t.title}"
        elif action.target_type == "decision":
            d = db.get(Decision, action.target_id)
            if d:
                target_name = f"D{d.id}: {d.text}"

        planned = _build_action_payload(db, action)

        actions_data.append({
            "id": action.id,
            "proposal_id": action.proposal_id,
            "action_type": action.action_type.value,
            "target_type": action.target_type,
            "target_id": action.target_id,
            "target_name": target_name or f"{action.target_type} #{action.target_id}",
            "payload": action.payload,
            "planned_payload": planned,
            "idempotency_key": action.idempotency_key,
            "state": action.state.value,
            "executed_at": action.executed_at.isoformat() if action.executed_at else None,
            "result": action.result,
        })

    return {
        "id": proposal.id,
        "trigger_type": proposal.trigger_type,
        "trigger_id": proposal.trigger_id,
        "summary": proposal.summary,
        "state": proposal.state.value,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        "decided_by": proposal.decided_by,
        "decided_at": proposal.decided_at.isoformat() if proposal.decided_at else None,
        "actions": actions_data,
    }


@router.get("/{proposal_id}/preview")
def preview_proposal_get(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dry-run preview endpoint returning the exact payloads that will be sent.
    """
    proposal = db.get(ChangeProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal #{proposal_id} not found")

    planned_actions = []
    for action in proposal.actions:
        if action.state == ActionState.rejected:
            continue
        planned_actions.append({
            "action_id": action.id,
            "action_type": action.action_type.value,
            "target_type": action.target_type,
            "target_id": action.target_id,
            "idempotency_key": action.idempotency_key,
            "payload": _build_action_payload(db, action),
        })

    return {
        "dry_run": True,
        "proposal_id": proposal.id,
        "state": proposal.state.value,
        "planned_actions": planned_actions,
    }


@router.post("/{proposal_id}/preview")
def preview_proposal_post(
    proposal_id: int,
    payload: PreviewProposalRequest = PreviewProposalRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dry-run preview endpoint taking optional selected action_ids and optional edited_payloads.
    """
    proposal = db.get(ChangeProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal #{proposal_id} not found")

    selected_ids = set(payload.action_ids) if payload.action_ids is not None else None
    edited_map = payload.edited_payloads or {}

    planned_actions = []
    for action in proposal.actions:
        if selected_ids is not None and action.id not in selected_ids:
            continue
        original_payload = dict(action.payload or {})
        if action.id in edited_map:
            original_payload.update(edited_map[action.id])
            action.payload = original_payload

        planned_payload = _build_action_payload(db, action)
        planned_actions.append({
            "action_id": action.id,
            "action_type": action.action_type.value,
            "target_type": action.target_type,
            "target_id": action.target_id,
            "idempotency_key": action.idempotency_key,
            "payload": planned_payload,
        })

    return {
        "dry_run": True,
        "proposal_id": proposal.id,
        "planned_actions": planned_actions,
    }


@router.post("/{proposal_id}/approve")
def approve_proposal(
    proposal_id: int,
    payload: ApproveProposalRequest = ApproveProposalRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approves the proposal with a list of action ids (partial approval allowed) and optional edited payloads.
    Only approved actions are executed by the executor.
    """
    proposal = db.get(ChangeProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal #{proposal_id} not found")

    alert = proposal.alerts[0] if proposal.alerts else None
    if alert and alert.meeting:
        verify_project_access(alert.meeting.project, current_user, db)

    if proposal.state == ProposalState.rejected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal #{proposal_id} was rejected and cannot be approved."
        )

    actor = payload.actor
    selected_ids: Optional[Set[int]] = None

    if payload.action_ids is not None:
        selected_ids = set(payload.action_ids)
    elif payload.actions is not None:
        selected_ids = {item.action_id for item in payload.actions}

    # Edited payloads map
    edited_map: Dict[int, Dict[str, Any]] = {}
    if payload.edited_payloads:
        edited_map.update(payload.edited_payloads)
    if payload.actions:
        for item in payload.actions:
            if item.edited_payload:
                edited_map[item.action_id] = item.edited_payload

    # Update actions
    for action in proposal.actions:
        if action.state == ActionState.executed:
            continue

        if selected_ids is not None:
            if action.id in selected_ids:
                if action.id in edited_map:
                    curr_p = dict(action.payload or {})
                    curr_p.update(edited_map[action.id])
                    action.payload = curr_p
                action.state = ActionState.approved
            else:
                action.state = ActionState.rejected
        else:
            if action.id in edited_map:
                curr_p = dict(action.payload or {})
                curr_p.update(edited_map[action.id])
                action.payload = curr_p
            action.state = ActionState.approved

    prev_state = proposal.state.value
    proposal.state = ProposalState.approved
    proposal.decided_by = actor
    proposal.decided_at = datetime.now(timezone.utc)
    db.flush()

    log(
        actor=actor,
        action="approve_proposal",
        entity_type="change_proposal",
        entity_id=proposal.id,
        before={"state": prev_state},
        after={"state": proposal.state.value, "decided_by": actor},
        db=db,
    )
    db.commit()

    # Execute approved actions using executor
    exec_res = execute_proposal(proposal.id, actor=actor, db=db)
    db.commit()

    return {
        "status": "executed",
        "proposal_id": proposal.id,
        "state": proposal.state.value,
        "execution": exec_res,
    }


@router.post("/{proposal_id}/reject")
def reject_proposal(
    proposal_id: int,
    payload: RejectProposalRequest = RejectProposalRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rejects the proposal and all its non-executed actions. Zero external calls are made (Invariant 2).
    """
    proposal = db.get(ChangeProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal #{proposal_id} not found")

    alert = proposal.alerts[0] if proposal.alerts else None
    if alert and alert.meeting:
        verify_project_access(alert.meeting.project, current_user, db)

    prev_state = proposal.state.value
    proposal.state = ProposalState.rejected
    proposal.decided_by = payload.actor
    proposal.decided_at = datetime.now(timezone.utc)

    for action in proposal.actions:
        if action.state != ActionState.executed:
            action.state = ActionState.rejected

    log(
        actor=payload.actor,
        action="reject_proposal",
        entity_type="change_proposal",
        entity_id=proposal.id,
        before={"state": prev_state},
        after={"state": proposal.state.value, "decided_by": payload.actor},
        db=db,
    )
    db.commit()

    return {
        "status": "rejected",
        "proposal_id": proposal.id,
        "state": proposal.state.value,
    }
