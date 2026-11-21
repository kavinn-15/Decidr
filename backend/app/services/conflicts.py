import logging
import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.models import Decision, Alert, Task, Item
from app.models.enums import (
    DecisionStatus,
    AlertKind,
    AlertState,
    LinkRelation,
    TaskStatus,
)
from app.llm import complete_json
from app.services.audit import log
from app.services.ledger import scope_overlap, search as search_decisions
from app.services.links import create_link

logger = logging.getLogger("decidr.conflicts")


class DecisionConflictJudgeOutput(BaseModel):
    verdict: Literal["contradicts", "supersedes", "duplicates", "consistent", "unrelated"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    old_quote: str
    new_quote: str


def notify_blast_radius_service(db: Session, decision: Decision, actor: str = "system") -> None:
    """
    Hook for the blast-radius service.
    When a decision is superseded or broken, downstream tasks and reminders are evaluated
    for cascading risk and repair proposals.
    """
    logger.info(f"[BLAST_RADIUS_HOOK] Feeding decision #{decision.id} ({decision.text}) to blast radius analysis.")


def _is_exact_substring(needle: str, *haystacks: Optional[str]) -> bool:
    """
    Verifies that needle is an exact non-empty substring of at least one haystack text.
    Invariant 6: Verbatim substring quote validation.
    """
    if not needle or not needle.strip():
        return False
    n = needle.strip()
    for h in haystacks:
        if h and n in h:
            return True
    return False


def detect_conflicts_for_decision(
    db: Session,
    decision: Decision,
    actor: str = "system",
    max_candidates: int = 5,
) -> List[Alert]:
    """
    When a decision is approved, find candidate earlier active decisions in the same project.
    - Scope filter first: if scope_overlap is disjoint, skip the LLM entirely (no alert, 0 calls).
    - Top 5 candidates by ledger.search.
    - Calls LLM judge per candidate returning verdict, confidence, explanation, and quotes.
    - Code validates quotes as exact substrings.
    - Behavior:
        * contradicts or supersedes with confidence >= 0.7 creates a conflict alert.
        * duplicates creates a low-priority 'possible duplicate' alert.
        * ambiguous (0.4 to 0.7) creates an alert asking the reviewer to decide.
        * consistent and unrelated create nothing.
    """
    if not decision or not decision.scope_project:
        return []

    # 1. Search for active decisions in the same project using BM25
    candidates_scored = search_decisions(
        db=db,
        project=decision.scope_project,
        text=decision.text,
        status=DecisionStatus.active,
        limit=15,
    )

    # Filter out self
    other_candidates = [
        hit["decision"]
        for hit in candidates_scored
        if hit["decision"].id != decision.id
    ]

    # 2. Scope filter: if scope is disjoint, skip LLM entirely (0 calls)
    eligible_candidates: List[Decision] = []
    for cand in other_candidates:
        overlap = scope_overlap(decision, cand)
        if overlap == "disjoint":
            logger.info(
                f"Candidate decision #{cand.id} scope is disjoint with #{decision.id} "
                f"({decision.scope_region} vs {cand.scope_region}). Skipping LLM call (0 calls)."
            )
            continue
        eligible_candidates.append(cand)

    # Top 5 eligible candidates
    eligible_candidates = eligible_candidates[:max_candidates]
    if not eligible_candidates:
        return []

    created_alerts: List[Alert] = []

    # 3. LLM judge call per candidate
    for cand in eligible_candidates:
        cand_quote = (
            cand.item.evidence_quote
            if cand.item and cand.item.evidence_quote
            else cand.text
        )
        dec_quote = (
            decision.item.evidence_quote
            if decision.item and decision.item.evidence_quote
            else decision.text
        )

        variables = {
            "project": decision.scope_project,
            "old_decision_text": cand.text,
            "old_decision_quote": cand_quote,
            "old_scope": f"region={cand.scope_region or 'all'}, release={cand.scope_release or 'all'}",
            "new_decision_text": decision.text,
            "new_decision_quote": dec_quote,
            "new_scope": f"region={decision.scope_region or 'all'}, release={decision.scope_release or 'all'}",
        }

        try:
            judge_res = complete_json(
                prompt_name="judge_decision_conflict",
                variables=variables,
                schema=DecisionConflictJudgeOutput,
            )
        except Exception as e:
            logger.warning(f"Failed LLM judge call for decisions #{decision.id} vs #{cand.id}: {e}")
            continue

        # 4. Code validates quotes as exact substrings (Invariant 6)
        cand_premise_texts = [p.text for p in cand.premises]
        cand_premise_quotes = [p.evidence_quote for p in cand.premises]
        old_valid = _is_exact_substring(
            judge_res.old_quote,
            cand.text,
            cand_quote,
            *cand_premise_texts,
            *cand_premise_quotes,
        )
        new_valid = _is_exact_substring(
            judge_res.new_quote,
            decision.text,
            dec_quote,
        )

        if not old_valid or not new_valid:
            logger.warning(
                f"Quote verification failed: old_valid={old_valid} ('{judge_res.old_quote}'), "
                f"new_valid={new_valid} ('{judge_res.new_quote}'). Dropping candidate hallucination."
            )
            continue

        # 5. Behavior routing
        verdict = judge_res.verdict
        conf = judge_res.confidence
        explanation_with_meta = f"{judge_res.explanation} <!-- old_decision_id:{cand.id} -->"

        if verdict in ("contradicts", "supersedes") and conf >= 0.7:
            # High-confidence conflict or supersession
            alert = Alert(
                kind=AlertKind.conflict,
                meeting_id=decision.item.meeting_id if decision.item else None,
                decision_id=decision.id,
                verdict=verdict,
                old_quote=judge_res.old_quote,
                new_quote=judge_res.new_quote,
                explanation=explanation_with_meta,
                state=AlertState.open,
            )
            db.add(alert)
            db.flush()

            if verdict == "supersedes":
                decision.supersedes_id = cand.id
                # Create unconfirmed supersedes link (Invariant 4)
                create_link(
                    db=db,
                    source_type="decision",
                    source_id=decision.id,
                    target_type="decision",
                    target_id=cand.id,
                    relation=LinkRelation.supersedes,
                    confirmed=False,
                    confidence=conf,
                    rationale=judge_res.explanation,
                    actor=actor,
                )

            log(
                actor=actor,
                action="create_conflict_alert",
                entity_type="alert",
                entity_id=alert.id,
                before=None,
                after={
                    "kind": alert.kind.value,
                    "verdict": alert.verdict,
                    "decision_id": alert.decision_id,
                    "target_decision_id": cand.id,
                    "confidence": conf,
                },
                db=db,
            )
            created_alerts.append(alert)

        elif verdict == "duplicates" and conf >= 0.7:
            # Low-priority possible duplicate card
            alert = Alert(
                kind=AlertKind.conflict,
                meeting_id=decision.item.meeting_id if decision.item else None,
                decision_id=decision.id,
                verdict="possible_duplicate",
                old_quote=judge_res.old_quote,
                new_quote=judge_res.new_quote,
                explanation=f"[Low Priority] Possible duplicate of Decision #{cand.id}: {explanation_with_meta}",
                state=AlertState.open,
            )
            db.add(alert)
            db.flush()

            log(
                actor=actor,
                action="create_duplicate_alert",
                entity_type="alert",
                entity_id=alert.id,
                before=None,
                after={
                    "kind": alert.kind.value,
                    "verdict": alert.verdict,
                    "decision_id": alert.decision_id,
                    "target_decision_id": cand.id,
                },
                db=db,
            )
            created_alerts.append(alert)

        elif 0.4 <= conf < 0.7 and verdict in ("contradicts", "supersedes", "duplicates"):
            # Ambiguous (0.4 to 0.7): creates card asking reviewer to decide
            alert = Alert(
                kind=AlertKind.conflict,
                meeting_id=decision.item.meeting_id if decision.item else None,
                decision_id=decision.id,
                verdict=f"ambiguous_{verdict}",
                old_quote=judge_res.old_quote,
                new_quote=judge_res.new_quote,
                explanation=f"[Reviewer confirmation needed] Potential {verdict} (confidence {conf:.2f}): {explanation_with_meta}",
                state=AlertState.open,
            )
            db.add(alert)
            db.flush()

            log(
                actor=actor,
                action="create_ambiguous_conflict_alert",
                entity_type="alert",
                entity_id=alert.id,
                before=None,
                after={
                    "kind": alert.kind.value,
                    "verdict": alert.verdict,
                    "decision_id": alert.decision_id,
                    "target_decision_id": cand.id,
                    "confidence": conf,
                },
                db=db,
            )
            created_alerts.append(alert)

        else:
            # Consistent or unrelated: create nothing
            logger.info(
                f"Candidate decision #{cand.id} vs #{decision.id} judged as '{verdict}' "
                f"(conf={conf:.2f}). No alert created."
            )

    return created_alerts


def approve_supersedes_alert(
    db: Session,
    alert_id: int,
    actor: str = "reviewer",
) -> Alert:
    """
    Approving a supersedes alert:
    1. Sets the old decision status=superseded.
    2. Creates a confirmed supersedes link.
    3. Marks its linked open tasks at_risk by feeding the old decision into
       the blast-radius service hook.
    4. Sets alert.state=confirmed.
    5. Writes audit log entries.
    """
    alert = db.get(Alert, alert_id)
    if not alert:
        raise ValueError(f"Alert #{alert_id} not found")

    new_decision = db.get(Decision, alert.decision_id) if alert.decision_id else None
    if not new_decision:
        raise ValueError(f"Alert #{alert_id} has no linked decision")

    # Extract target/old decision id
    old_decision_id = None
    if alert.explanation:
        match = re.search(r"<!-- old_decision_id:(\d+) -->", alert.explanation)
        if match:
            old_decision_id = int(match.group(1))

    if not old_decision_id and new_decision.supersedes_id:
        old_decision_id = new_decision.supersedes_id

    old_decision = db.get(Decision, old_decision_id) if old_decision_id else None
    if not old_decision:
        raise ValueError(f"Old decision for supersedes alert #{alert_id} could not be resolved.")

    # 1. Update old decision status to superseded
    prev_status = old_decision.status.value
    old_decision.status = DecisionStatus.superseded
    new_decision.supersedes_id = old_decision.id

    log(
        actor=actor,
        action="supersede_decision",
        entity_type="decision",
        entity_id=old_decision.id,
        before={"status": prev_status},
        after={"status": old_decision.status.value, "superseded_by": new_decision.id},
        db=db,
    )

    # 2. Create/confirm supersedes link
    create_link(
        db=db,
        source_type="decision",
        source_id=new_decision.id,
        target_type="decision",
        target_id=old_decision.id,
        relation=LinkRelation.supersedes,
        confirmed=True,
        confidence=1.0,
        rationale=f"Supersedes confirmed via Alert #{alert.id}",
        actor=actor,
    )

    # 3. Mark linked open tasks at_risk
    for task in old_decision.tasks:
        if task.status == TaskStatus.open:
            task_prev = task.status.value
            task.status = TaskStatus.at_risk
            log(
                actor=actor,
                action="mark_task_at_risk",
                entity_type="task",
                entity_id=task.id,
                before={"status": task_prev},
                after={"status": task.status.value, "reason": f"Decision #{old_decision.id} superseded"},
                db=db,
            )

    # Feed old decision into blast-radius service hook
    notify_blast_radius_service(db, old_decision, actor=actor)

    # 4. Confirm alert
    alert_before = {"state": alert.state.value}
    alert.state = AlertState.confirmed

    log(
        actor=actor,
        action="confirm_alert",
        entity_type="alert",
        entity_id=alert.id,
        before=alert_before,
        after={"state": alert.state.value, "superseded_decision_id": old_decision.id},
        db=db,
    )

    db.flush()
    return alert
