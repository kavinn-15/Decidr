from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.models import (
    ChangeProposal,
    ChangeAction,
    Task,
    Decision,
    Reminder,
)
from app.models.enums import (
    ProposalState,
    ActionState,
    ActionType,
    TaskStatus,
    DecisionStatus,
    ReminderState,
)
from app.trackers.base import BaseTracker
from app.trackers import get_tracker
from app.services.audit import log


class ProposalNotApprovedError(Exception):
    """Raised when an attempt is made to execute a proposal that is not in state 'approved'."""
    pass


class ExecutionError(Exception):
    """Raised when an error occurs during proposal execution."""
    pass


def _build_action_payload(session: Session, action: ChangeAction) -> dict[str, Any]:
    """
    Constructs the exact payload that would be sent for an action (used in dry_run and execution).
    """
    atype = action.action_type
    payload = action.payload or {}

    if atype == ActionType.create_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        title = payload.get("title", task.title if task else "Untitled Task")
        body = payload.get("description", task.description if task else "")
        assignee = payload.get("assignee")
        if not assignee and task and task.owner:
            assignee = task.owner.tracker_id or task.owner.email
        due_date = payload.get(
            "due_date",
            task.due_date.isoformat() if task and task.due_date else None,
        )
        labels = payload.get("labels", ["decidr"])
        return {
            "type": "tracker.create_issue",
            "title": title,
            "body": body,
            "assignee": assignee,
            "due_date": due_date,
            "labels": labels,
            "idempotency_key": action.idempotency_key,
        }

    elif atype == ActionType.comment_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        ref = payload.get("tracker_ref") or (task.tracker_ref if task else None)
        text = payload.get("text") or payload.get("comment", "")
        return {
            "type": "tracker.add_comment",
            "ref": ref,
            "text": text,
            "idempotency_key": action.idempotency_key,
        }

    elif atype == ActionType.reopen_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        ref = payload.get("tracker_ref") or (task.tracker_ref if task else None)
        return {
            "type": "tracker.reopen",
            "ref": ref,
            "task_id": action.target_id,
            "idempotency_key": action.idempotency_key,
        }

    elif atype == ActionType.cancel_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        ref = payload.get("tracker_ref") or (task.tracker_ref if task else None)
        return {
            "type": "tracker.cancel",
            "ref": ref,
            "task_id": action.target_id,
            "idempotency_key": action.idempotency_key,
        }

    elif atype == ActionType.mark_decision_at_risk:
        return {
            "type": "local.mark_decision_at_risk",
            "decision_id": action.target_id,
            "status": "at_risk",
            "idempotency_key": action.idempotency_key,
        }

    elif atype == ActionType.pause_reminders:
        reminders = (
            session.query(Reminder)
            .filter(
                Reminder.task_id == action.target_id,
                Reminder.state == ReminderState.pending,
            )
            .all()
        )
        return {
            "type": "local.pause_reminders",
            "task_id": action.target_id,
            "reminder_ids": [r.id for r in reminders],
            "reason": payload.get("reason") or payload.get("pause_reason", "Proposal executed: paused reminders"),
            "idempotency_key": action.idempotency_key,
        }

    else:
        return {
            "type": f"unknown.{atype.value}",
            "payload": payload,
            "idempotency_key": action.idempotency_key,
        }


def _execute_single_action(
    session: Session,
    action: ChangeAction,
    tracker: BaseTracker,
) -> dict[str, Any]:
    """
    Executes a single action against the tracker or local models.
    """
    atype = action.action_type
    payload = action.payload or {}

    if atype == ActionType.create_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        title = payload.get("title", task.title if task else "Untitled Task")
        body = payload.get("description", task.description if task else "")
        assignee = payload.get("assignee")
        if not assignee and task and task.owner:
            assignee = task.owner.tracker_id or task.owner.email
        due_date = payload.get(
            "due_date",
            task.due_date.isoformat() if task and task.due_date else None,
        )
        labels = payload.get("labels", ["decidr"])

        tracker_res = tracker.create_issue(
            title=title,
            body=body,
            assignee=assignee,
            due_date=due_date,
            labels=labels,
            idempotency_key=action.idempotency_key,
        )
        if task:
            task.tracker_ref = tracker_res.get("ref")
            task.tracker_url = tracker_res.get("url")
            if "provisional" in payload:
                task.provisional = payload["provisional"]
            elif "provisional" in labels:
                task.provisional = True
            else:
                task.provisional = False
        return tracker_res

    elif atype == ActionType.comment_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        ref = payload.get("tracker_ref") or (task.tracker_ref if task else None)
        text = payload.get("text") or payload.get("comment", "")
        if not ref:
            raise ValueError(f"Cannot comment on task {action.target_id}: no tracker_ref found")
        tracker.add_comment(ref=ref, text=text)
        return {"ref": ref, "comment": text}

    elif atype == ActionType.reopen_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        ref = payload.get("tracker_ref") or (task.tracker_ref if task else None)
        if ref:
            tracker.reopen(ref=ref)
        if task:
            task.status = TaskStatus.open
        return {"ref": ref, "status": "open"}

    elif atype == ActionType.cancel_task:
        task = session.get(Task, action.target_id) if action.target_type == "task" else None
        ref = payload.get("tracker_ref") or (task.tracker_ref if task else None)
        if ref:
            tracker.cancel(ref=ref)
        if task:
            task.status = TaskStatus.cancelled
        return {"ref": ref, "status": "cancelled"}

    elif atype == ActionType.mark_decision_at_risk:
        decision = session.get(Decision, action.target_id) if action.target_type == "decision" else None
        if not decision:
            raise ValueError(f"Decision {action.target_id} not found")
        decision.status = DecisionStatus.at_risk
        return {"decision_id": decision.id, "status": "at_risk"}

    elif atype == ActionType.pause_reminders:
        reminders = (
            session.query(Reminder)
            .filter(
                Reminder.task_id == action.target_id,
                Reminder.state == ReminderState.pending,
            )
            .all()
        )
        paused_ids = []
        reason = payload.get("reason") or payload.get("pause_reason", "Proposal executed: paused reminders")
        for r in reminders:
            r.state = ReminderState.paused
            r.pause_reason = reason
            paused_ids.append(r.id)
        return {"task_id": action.target_id, "paused_reminder_ids": paused_ids}

    else:
        raise ValueError(f"Unsupported action type: {atype}")


def execute_proposal(
    proposal_id: int,
    actor: str,
    dry_run: bool = False,
    db: Optional[Session] = None,
    tracker: Optional[BaseTracker] = None,
) -> dict[str, Any]:
    """
    Executes an approved proposal and its associated change actions.

    Invariants enforced:
    - Invariant 2: Must raise unless the proposal state is approved. Draft or rejected proposals
      cause zero external calls.
    - Invariant 3: Idempotent execution via unique idempotency_key. Running twice creates nothing new.
    - Invariant 7: Every state change writes an audit_log row.
    - Error Isolation: A failed action does not halt or roll back other actions.
    - Retries: Re-running retries only failed actions; successful ones are not duplicated.
    - Dry Run: Returns exact payload without calling external systems or modifying data.
    """
    session = db if db is not None else SessionLocal()
    should_close = db is None

    try:
        proposal = session.get(ChangeProposal, proposal_id)
        if not proposal:
            raise ValueError(f"ChangeProposal with id {proposal_id} not found")

        # Invariant 2: Never write to external system unless proposal is approved.
        # Allow ProposalState.executed only for idempotent replay.
        if proposal.state not in (ProposalState.approved, ProposalState.executed):
            raise ProposalNotApprovedError(
                f"Proposal {proposal_id} cannot be executed because it is in state '{proposal.state.value}'. "
                f"Only proposals in state 'approved' can be executed."
            )

        # Dry Run Mode: Return planned payloads without executing anything
        if dry_run:
            planned_actions = []
            skipped_count = 0
            for action in proposal.actions:
                if action.state == ActionState.executed:
                    skipped_count += 1
                    continue
                if action.state in (ActionState.draft, ActionState.rejected):
                    continue

                planned_payload = _build_action_payload(session, action)
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
                "actor": actor,
                "planned_actions": planned_actions,
                "executed_count": 0,
                "skipped_count": skipped_count,
                "failed_count": 0,
            }

        # Live Execution
        active_tracker = tracker or get_tracker(db=session)
        executed_count = 0
        skipped_count = 0
        failed_count = 0

        for action in proposal.actions:
            # 1. Skip if this action is already executed
            if action.state == ActionState.executed:
                skipped_count += 1
                continue

            # 2. Skip if another action with the same idempotency_key is already executed (Invariant 3)
            already_executed = (
                session.query(ChangeAction)
                .filter(
                    ChangeAction.idempotency_key == action.idempotency_key,
                    ChangeAction.state == ActionState.executed,
                    ChangeAction.id != action.id,
                )
                .first()
            )
            if already_executed:
                action.state = ActionState.executed
                action.result = already_executed.result
                action.executed_at = datetime.now(timezone.utc)
                session.flush()
                skipped_count += 1
                continue

            # 3. Only execute approved or failed (retry) actions
            if action.state not in (ActionState.approved, ActionState.failed):
                continue

            before_state = {
                "state": action.state.value,
                "result": action.result,
                "executed_at": action.executed_at.isoformat() if action.executed_at else None,
            }

            try:
                res = _execute_single_action(session, action, active_tracker)
                action.state = ActionState.executed
                action.result = res
                action.executed_at = datetime.now(timezone.utc)
                session.flush()

                # Audit Log row (Invariant 7)
                log(
                    actor=actor,
                    action=f"execute_action:{action.action_type.value}",
                    entity_type="change_action",
                    entity_id=action.id,
                    before=before_state,
                    after={
                        "state": action.state.value,
                        "result": action.result,
                        "executed_at": action.executed_at.isoformat(),
                    },
                    db=session,
                )
                executed_count += 1

            except Exception as err:
                action.state = ActionState.failed
                action.result = {"error": str(err)}
                session.flush()

                log(
                    actor=actor,
                    action=f"execute_action_failed:{action.action_type.value}",
                    entity_type="change_action",
                    entity_id=action.id,
                    before=before_state,
                    after={
                        "state": action.state.value,
                        "error": str(err),
                    },
                    db=session,
                )
                failed_count += 1

        # Check if all actionable items are now executed
        unexecuted = [
            a for a in proposal.actions
            if a.state in (ActionState.approved, ActionState.failed)
        ]
        if not unexecuted and any(a.state == ActionState.executed for a in proposal.actions):
            prev_prop_state = proposal.state.value
            proposal.state = ProposalState.executed
            proposal.decided_by = proposal.decided_by or actor
            proposal.decided_at = proposal.decided_at or datetime.now(timezone.utc)
            session.flush()

            log(
                actor=actor,
                action="execute_proposal",
                entity_type="change_proposal",
                entity_id=proposal.id,
                before={"state": prev_prop_state},
                after={"state": proposal.state.value},
                db=session,
            )

        if should_close:
            session.commit()
        else:
            session.flush()

        return {
            "dry_run": False,
            "proposal_id": proposal.id,
            "actor": actor,
            "executed_count": executed_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "proposal_state": proposal.state.value,
        }

    finally:
        if should_close:
            session.close()
