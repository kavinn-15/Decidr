import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm import complete_json
from app.models.models import (
    Alert,
    ChangeProposal,
    ChangeAction,
    Premise,
    Decision,
    Task,
    Utterance,
    Meeting,
)
from app.models.enums import (
    AlertKind,
    ProposalState,
    ActionType,
    ActionState,
    TaskStatus,
    DecisionStatus,
)
from app.services.audit import log
from app.services.blast_radius import calculate_blast_radius

logger = logging.getLogger("decidr.repair")


def make_idempotency_key(alert_id: int, action_type: ActionType | str, target_id: int) -> str:
    """
    Every action has idempotency_key = hash(alert_id, action_type, target_id).
    """
    atype_val = action_type.value if hasattr(action_type, "value") else str(action_type)
    raw = f"{alert_id}:{atype_val}:{target_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TaskSuggestion(BaseModel):
    title: str = Field(description="Actionable title for replacement work")
    description: str = Field(description="Description of replacement work")
    target_task_id: Optional[int] = Field(default=None, description="Optional ID of affected task being replaced")


class RepairSuggestionsResponse(BaseModel):
    suggestions: List[TaskSuggestion] = Field(default_factory=list)


def generate_repair_plan(
    db: Session,
    alert_id: int,
    actor: str = "system",
    suggest_replacements: bool = True,
) -> ChangeProposal:
    """
    Generates a deterministic rule-based repair plan (ChangeProposal in state draft) for a Premise Break alert.

    Invariants enforced:
    - Rule-based generation (Invariant 5):
      1. For each affected task with a tracker ticket, a comment_task action
         (text states the broken premise, new quote, speaker and date).
      2. mark_decision_at_risk for each affected decision.
      3. pause_reminders for each affected task.
      4. reopen_task for affected tasks marked done.
      5. The LLM may ONLY draft optional create_task suggestions for replacement work
         (title and description); code adds them as draft actions with owner and deadline null and flags them.
    - Idempotency (Invariant 3):
      Every action has idempotency_key = hash(alert_id, action_type, target_id).
    - Safety (Invariant 2):
      Proposal is in state 'draft', requiring human review before execution.
    - Audit Trail (Invariant 7):
      Logs creation in append-only audit log.
    """
    alert = db.get(Alert, alert_id)
    if not alert:
        raise ValueError(f"Alert #{alert_id} not found")

    # If proposal already exists for this alert in draft, reuse it
    existing_proposal = (
        db.query(ChangeProposal)
        .filter(
            ChangeProposal.trigger_type == "alert",
            ChangeProposal.trigger_id == alert.id,
            ChangeProposal.state.in_([ProposalState.draft, ProposalState.approved, ProposalState.executed]),
        )
        .first()
    )
    if existing_proposal:
        return existing_proposal

    # Compute blast radius
    blast_info = calculate_blast_radius(db, alert_id=alert.id)

    root_premise_text = blast_info.get("root_cause", {}).get("text", "Unknown premise")
    premise_id_val = blast_info.get("root_cause", {}).get("id", alert.premise_id)
    trigger_evidence = blast_info.get("trigger_evidence", {})
    speaker = trigger_evidence.get("speaker") or "Participant"
    meeting_date = trigger_evidence.get("meeting_date") or ""
    new_quote = trigger_evidence.get("new_quote") or alert.new_quote or ""

    summary = f"Repair plan for broken premise P{premise_id_val}: \"{root_premise_text}\""
    proposal = ChangeProposal(
        trigger_type="alert",
        trigger_id=alert.id,
        summary=summary,
        state=ProposalState.draft,
        created_at=datetime.now(timezone.utc),
    )
    db.add(proposal)
    db.flush()
    alert.proposal_id = proposal.id

    actions: List[ChangeAction] = []
    added_keys: Set[str] = set()

    # Rule 1: mark_decision_at_risk for each affected decision
    affected_decisions = blast_info.get("affected_decisions", [])
    if not affected_decisions and alert.decision_id:
        root_d = db.get(Decision, alert.decision_id)
        if root_d:
            affected_decisions = [{"id": root_d.id, "text": root_d.text}]

    for dec in affected_decisions:
        d_id = dec["id"]
        ikey = make_idempotency_key(alert.id, ActionType.mark_decision_at_risk, d_id)
        if ikey not in added_keys:
            added_keys.add(ikey)
            act = ChangeAction(
                proposal_id=proposal.id,
                action_type=ActionType.mark_decision_at_risk,
                target_type="decision",
                target_id=d_id,
                payload={
                    "decision_id": d_id,
                    "status": "at_risk",
                    "reason": f"Underlying premise P{premise_id_val} broken ({new_quote})",
                },
                idempotency_key=ikey,
                state=ActionState.draft,
            )
            db.add(act)
            actions.append(act)

    # Rule 2: for each affected task with a tracker ticket, a comment_task action
    # Text states the broken premise, the new quote, the speaker and date.
    affected_tasks = blast_info.get("affected", [])
    comment_text = (
        f"Premise Break Alert: Underlying premise \"{root_premise_text}\" broken. "
        f"New evidence from {speaker} ({meeting_date}): \"{new_quote}\""
    )

    for task_info in affected_tasks:
        t_id = task_info["id"]
        task_obj = db.get(Task, t_id)
        if task_obj and task_obj.tracker_ref:
            ikey = make_idempotency_key(alert.id, ActionType.comment_task, t_id)
            if ikey not in added_keys:
                added_keys.add(ikey)
                act = ChangeAction(
                    proposal_id=proposal.id,
                    action_type=ActionType.comment_task,
                    target_type="task",
                    target_id=t_id,
                    payload={
                        "tracker_ref": task_obj.tracker_ref,
                        "comment": comment_text,
                        "text": comment_text,
                    },
                    idempotency_key=ikey,
                    state=ActionState.draft,
                )
                db.add(act)
                actions.append(act)

    # Rule 2b: mark_task_at_risk for each affected task
    for task_info in affected_tasks:
        t_id = task_info["id"]
        ikey = make_idempotency_key(alert.id, ActionType.mark_task_at_risk, t_id)
        if ikey not in added_keys:
            added_keys.add(ikey)
            act = ChangeAction(
                proposal_id=proposal.id,
                action_type=ActionType.mark_task_at_risk,
                target_type="task",
                target_id=t_id,
                payload={
                    "task_id": t_id,
                    "status": "at_risk",
                    "reason": f"Underlying premise P{premise_id_val} broken: {root_premise_text}",
                },
                idempotency_key=ikey,
                state=ActionState.draft,
            )
            db.add(act)
            actions.append(act)

    # Rule 3: pause_reminders for each affected task
    pause_reason = f"Pending contract SLA clarification or premise resolution for P{premise_id_val}: {root_premise_text}"
    for task_info in affected_tasks:
        t_id = task_info["id"]
        ikey = make_idempotency_key(alert.id, ActionType.pause_reminders, t_id)
        if ikey not in added_keys:
            added_keys.add(ikey)
            act = ChangeAction(
                proposal_id=proposal.id,
                action_type=ActionType.pause_reminders,
                target_type="task",
                target_id=t_id,
                payload={
                    "task_id": t_id,
                    "pause_reason": pause_reason,
                    "reason": pause_reason,
                },
                idempotency_key=ikey,
                state=ActionState.draft,
            )
            db.add(act)
            actions.append(act)

    # Rule 4: reopen_task for affected tasks marked done
    for task_info in affected_tasks:
        t_id = task_info["id"]
        task_obj = db.get(Task, t_id)
        if task_obj and task_obj.status == TaskStatus.done:
            ikey = make_idempotency_key(alert.id, ActionType.reopen_task, t_id)
            if ikey not in added_keys:
                added_keys.add(ikey)
                act = ChangeAction(
                    proposal_id=proposal.id,
                    action_type=ActionType.reopen_task,
                    target_type="task",
                    target_id=t_id,
                    payload={
                        "task_id": t_id,
                        "tracker_ref": task_obj.tracker_ref,
                        "reason": f"Reopening task due to broken premise: {root_premise_text}",
                    },
                    idempotency_key=ikey,
                    state=ActionState.draft,
                )
                db.add(act)
                actions.append(act)

    # Rule 5: Optional replacement task suggestions via LLM
    if suggest_replacements:
        try:
            llm_res: RepairSuggestionsResponse = complete_json(
                prompt_name="suggest_repair_tasks.v1.txt",
                variables={
                    "premise_text": root_premise_text,
                    "new_quote": new_quote,
                    "speaker": speaker,
                    "meeting_date": meeting_date,
                    "affected_decisions": "\n".join(f"- D{d['id']}: {d.get('text', '')}" for d in affected_decisions),
                    "affected_tasks": "\n".join(f"- T{t['id']}: {t.get('title', '')}" for t in affected_tasks),
                },
                schema=RepairSuggestionsResponse,
            )
            if llm_res and llm_res.suggestions:
                for s in llm_res.suggestions:
                    target_id = s.target_task_id or (affected_tasks[0]["id"] if affected_tasks else 0)
                    ikey = make_idempotency_key(alert.id, ActionType.create_task, target_id)
                    if ikey not in added_keys:
                        added_keys.add(ikey)
                        act = ChangeAction(
                            proposal_id=proposal.id,
                            action_type=ActionType.create_task,
                            target_type="task",
                            target_id=target_id,
                            payload={
                                "title": s.title,
                                "description": s.description,
                                "owner": None,
                                "deadline": None,
                                "needs_owner": True,
                                "needs_deadline": True,
                                "is_suggestion": True,
                            },
                            idempotency_key=ikey,
                            state=ActionState.draft,
                        )
                        db.add(act)
                        actions.append(act)
        except Exception as err:
            logger.info(f"LLM replacement suggestions skipped: {err}")

    db.flush()

    # Invariant 7: Audit row for repair proposal creation
    log(
        actor=actor,
        action="generate_repair_plan",
        entity_type="change_proposal",
        entity_id=proposal.id,
        before={},
        after={"state": proposal.state.value, "actions_count": len(actions)},
        db=db,
    )

    return proposal
