from datetime import date, datetime
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import dateparser
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.adapter import complete_json
from app.models.enums import (
    ItemType,
    ReviewState,
    DecisionStatus,
    PremiseState,
    PremiseStatus,
    LinkRelation,
    TaskStatus,
    MeetingStatus,
)
from app.models.models import Meeting, Utterance, Person, Item, Decision, Premise, Task, Link
from app.services.audit import log as audit_log
from app.services.ingestion import map_speaker

logger = logging.getLogger("decidr.extraction")


# --- Pass 1 Schemas ---
class DecisionExtracted(BaseModel):
    text: str
    evidence_quote: str
    utterance_idx: int
    confidence: float = 1.0
    region_mentioned: Optional[str] = None
    release_mentioned: Optional[str] = None


class ActionExtracted(BaseModel):
    text: str
    owner_name: Optional[str] = None
    deadline_phrase: Optional[str] = None
    evidence_quote: str
    utterance_idx: int
    confidence: float = 1.0
    related_decision_hint: Optional[str] = None


class Pass1Output(BaseModel):
    decisions: List[DecisionExtracted] = Field(default_factory=list)
    actions: List[ActionExtracted] = Field(default_factory=list)


# --- Pass 2 Schemas ---
class PremiseExtracted(BaseModel):
    text: str
    evidence_quote: str
    utterance_idx: int
    valid_until_phrase: Optional[str] = None


class Pass2Output(BaseModel):
    premises: List[PremiseExtracted] = Field(default_factory=list)


def resolve_relative_date(phrase: Optional[str], meeting_date: date) -> Optional[date]:
    """
    Resolve relative phrases ('next Friday', 'by Nov 20') against meeting date
    using dateparser. Stored strictly as ISO date (Invariant 8).
    """
    if not phrase or not phrase.strip():
        return None

    clean = phrase.strip()
    # Strip common leading temporal prepositions
    clean = re.sub(r'^(?:by|before|on|until|due|at)\s+', '', clean, flags=re.IGNORECASE)
    base_dt = datetime.combine(meeting_date, datetime.min.time())

    # Dateparser configuration
    parsed = dateparser.parse(
        clean,
        settings={
            "RELATIVE_BASE": base_dt,
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    if parsed:
        return parsed.date()
    return None


def verify_and_align_quote(
    evidence_quote: str,
    cited_idx: int,
    utterances_by_idx: Dict[int, Utterance],
) -> Tuple[bool, Optional[Utterance]]:
    """
    Invariant 6: Verify evidence_quote is an exact substring of the cited utterance.
    If slightly offset, check nearby utterances. If not an exact substring anywhere,
    fail verification and discard the item.
    """
    if not evidence_quote or not evidence_quote.strip():
        return False, None

    quote = evidence_quote.strip()

    # 1. Check cited utterance first
    target_utt = utterances_by_idx.get(cited_idx)
    if target_utt and quote in target_utt.text:
        return True, target_utt

    # 2. Check immediately adjacent utterances (idx - 1, idx + 1)
    for offset in (-1, 1, -2, 2):
        neighbor = utterances_by_idx.get(cited_idx + offset)
        if neighbor and quote in neighbor.text:
            return True, neighbor

    # 3. Check all utterances in meeting
    for u in utterances_by_idx.values():
        if quote in u.text:
            return True, u

    return False, None


def chunk_utterances(utterances: List[Utterance], chunk_size: int = 40, overlap: int = 5) -> List[List[Utterance]]:
    """Split utterances into overlapping chunks."""
    if not utterances:
        return []
    if len(utterances) <= chunk_size:
        return [utterances]

    chunks = []
    start = 0
    step = chunk_size - overlap
    while start < len(utterances):
        chunk = utterances[start : start + chunk_size]
        chunks.append(chunk)
        if start + chunk_size >= len(utterances):
            break
        start += step
    return chunks


def normalize_text_key(text: str) -> str:
    """Normalize text for deduplication."""
    return re.sub(r'\W+', '', text.lower())


def extract_meeting_items(db: Session, meeting_id: int, actor: str = "system") -> Dict[str, Any]:
    """
    Run two-pass extraction on meeting utterances:
    Pass 1: Decisions & Actions on ~40 utterance chunks.
    Pass 2: Premises per extracted decision using surrounding context.
    Post-processing:
    - Verifies quotes (Invariant 6 - drops fabricated quotes).
    - Merges duplicates across overlapping chunks.
    - Resolves dates against meeting date (Invariant 8).
    - Maps owners and flags missing owners/deadlines (Invariant 1).
    - Sets explicit scopes (Invariant 9).
    - Creates task-to-decision links with confidence ratings.
    - Updates meeting status: uploaded -> processing -> review.
    """
    meeting = db.query(Meeting).filter_by(id=meeting_id).first()
    if not meeting:
        raise ValueError(f"Meeting {meeting_id} not found.")

    meeting.status = MeetingStatus.processing
    db.commit()

    try:
        utterances = (
            db.query(Utterance)
            .filter_by(meeting_id=meeting_id)
            .order_by(Utterance.idx.asc())
            .all()
        )
        if not utterances:
            meeting.status = MeetingStatus.review
            db.commit()
            return {"decisions_count": 0, "actions_count": 0, "premises_count": 0, "dropped_quotes": 0}

        utterances_by_idx = {u.idx: u for u in utterances}
        people = db.query(Person).all()

        # Pass 1: Extract Decisions and Actions over chunks
        chunks = chunk_utterances(utterances, chunk_size=40, overlap=5)
        raw_decisions: List[DecisionExtracted] = []
        raw_actions: List[ActionExtracted] = []

        for chunk in chunks:
            chunk_text = "\n".join(
                [f"[{u.idx}] {u.speaker_raw}: {u.text}" for u in chunk]
            )
            pass1_result: Pass1Output = complete_json(
                prompt_name="extract_pass1",
                variables={
                    "project": meeting.project,
                    "meeting_date": str(meeting.date),
                    "transcript_chunk": chunk_text,
                },
                schema=Pass1Output,
            )
            raw_decisions.extend(pass1_result.decisions)
            raw_actions.extend(pass1_result.actions)

        # Post-Processing: Verify quotes & merge duplicates
        dropped_quotes_count = 0

        # Process Decisions
        verified_decisions: List[Tuple[DecisionExtracted, Utterance]] = []
        seen_decision_keys: Set[str] = set()

        for d in raw_decisions:
            is_valid, matched_utt = verify_and_align_quote(d.evidence_quote, d.utterance_idx, utterances_by_idx)
            if not is_valid or matched_utt is None:
                logger.warning(
                    f"Invariant 6 Violation: Dropping fabricated decision quote '{d.evidence_quote}' in utterance {d.utterance_idx}"
                )
                dropped_quotes_count += 1
                continue

            dedup_key = normalize_text_key(d.evidence_quote)
            if dedup_key in seen_decision_keys:
                continue
            seen_decision_keys.add(dedup_key)
            verified_decisions.append((d, matched_utt))

        # Process Actions
        verified_actions: List[Tuple[ActionExtracted, Utterance]] = []
        seen_action_keys: Set[str] = set()

        for a in raw_actions:
            is_valid, matched_utt = verify_and_align_quote(a.evidence_quote, a.utterance_idx, utterances_by_idx)
            if not is_valid or matched_utt is None:
                logger.warning(
                    f"Invariant 6 Violation: Dropping fabricated action quote '{a.evidence_quote}' in utterance {a.utterance_idx}"
                )
                dropped_quotes_count += 1
                continue

            dedup_key = normalize_text_key(a.evidence_quote)
            if dedup_key in seen_action_keys:
                continue
            seen_action_keys.add(dedup_key)
            verified_actions.append((a, matched_utt))

        # Pass 2: Extract Premises per verified decision
        saved_decisions: List[Decision] = []

        for d_extracted, d_utt in verified_decisions:
            # Create Item & Decision rows
            decision_item = Item(
                meeting_id=meeting.id,
                type=ItemType.decision,
                text=d_extracted.text,
                confidence=d_extracted.confidence,
                evidence_quote=d_extracted.evidence_quote,
                utterance_id=d_utt.id,
                review_state=ReviewState.proposed,
                needs_owner=False,
                needs_deadline=False,
            )
            db.add(decision_item)
            db.flush()

            # Scope determination (Invariant 9)
            scope_region = d_extracted.region_mentioned or meeting.region
            scope_release = d_extracted.release_mentioned or meeting.release

            decision_model = Decision(
                item_id=decision_item.id,
                text=d_extracted.text,
                scope_project=meeting.project,
                scope_region=scope_region,
                scope_release=scope_release,
                effective_from=meeting.date,
                status=DecisionStatus.active,
                version=1,
            )
            db.add(decision_model)
            db.flush()
            saved_decisions.append(decision_model)

            # Context window for premise extraction: ~10 surrounding utterances
            start_idx = max(0, d_utt.idx - 5)
            end_idx = min(len(utterances), d_utt.idx + 6)
            context_utts = utterances[start_idx:end_idx]
            context_text = "\n".join([f"[{u.idx}] {u.speaker_raw}: {u.text}" for u in context_utts])

            pass2_result: Pass2Output = complete_json(
                prompt_name="extract_pass2_premises",
                variables={
                    "project": meeting.project,
                    "meeting_date": str(meeting.date),
                    "decision_text": d_extracted.text,
                    "decision_quote": d_extracted.evidence_quote,
                    "context_utterances": context_text,
                },
                schema=Pass2Output,
            )

            # Verify and save premises
            seen_premise_keys: Set[str] = set()
            for p_extracted in pass2_result.premises:
                p_valid, p_matched_utt = verify_and_align_quote(
                    p_extracted.evidence_quote, p_extracted.utterance_idx, utterances_by_idx
                )
                if not p_valid or p_matched_utt is None:
                    logger.warning(
                        f"Invariant 6 Violation: Dropping fabricated premise quote '{p_extracted.evidence_quote}'"
                    )
                    dropped_quotes_count += 1
                    continue

                p_key = normalize_text_key(p_extracted.evidence_quote)
                if p_key in seen_premise_keys:
                    continue
                seen_premise_keys.add(p_key)

                # Resolve valid_until date if present
                valid_until_date = resolve_relative_date(p_extracted.valid_until_phrase, meeting.date)

                premise_model = Premise(
                    decision_id=decision_model.id,
                    text=p_extracted.text,
                    evidence_quote=p_extracted.evidence_quote,
                    utterance_id=p_matched_utt.id,
                    scope_project=decision_model.scope_project,
                    scope_region=decision_model.scope_region,
                    valid_from=meeting.date,
                    valid_until=valid_until_date,
                    state=PremiseState.proposed,
                    status=PremiseStatus.holding,
                )
                db.add(premise_model)

        # Save Actions and Tasks
        saved_tasks: List[Tuple[Task, Optional[str]]] = []

        for a_extracted, a_utt in verified_actions:
            # Owner mapping (Invariant 1: never guess)
            owner_id = None
            needs_owner = True
            if a_extracted.owner_name and a_extracted.owner_name.strip():
                pid, mapped = map_speaker(a_extracted.owner_name, people)
                if mapped and pid is not None:
                    owner_id = pid
                    needs_owner = False

            # Deadline resolution (Invariant 8)
            deadline_date = resolve_relative_date(a_extracted.deadline_phrase, meeting.date)
            needs_deadline = deadline_date is None

            action_item = Item(
                meeting_id=meeting.id,
                type=ItemType.action,
                text=a_extracted.text,
                owner_id=owner_id,
                deadline=deadline_date,
                needs_owner=needs_owner,
                needs_deadline=needs_deadline,
                confidence=a_extracted.confidence,
                evidence_quote=a_extracted.evidence_quote,
                utterance_id=a_utt.id,
                review_state=ReviewState.proposed,
            )
            db.add(action_item)
            db.flush()

            task_model = Task(
                item_id=action_item.id,
                decision_id=None,  # Will link below
                title=a_extracted.text,
                owner_id=owner_id,
                due_date=deadline_date,
                provisional=True,
                status=TaskStatus.open,
            )
            db.add(task_model)
            db.flush()
            saved_tasks.append((task_model, a_extracted.related_decision_hint))

        # Establish Task-to-Decision Links
        for task_model, decision_hint in saved_tasks:
            best_decision = None
            confidence = 0.5
            rationale = "Candidate link"

            if saved_decisions:
                # If explicit hint provided or only 1 decision
                if decision_hint and decision_hint.strip():
                    hint_lower = decision_hint.lower()
                    for d in saved_decisions:
                        if any(token in d.text.lower() for token in hint_lower.split() if len(token) > 3):
                            best_decision = d
                            confidence = 0.85
                            rationale = f"Matched related decision hint: {decision_hint}"
                            break

                # Fallback to text overlap match
                if not best_decision:
                    task_tokens = set(re.findall(r'\w{4,}', task_model.title.lower()))
                    best_overlap = 0
                    for d in saved_decisions:
                        d_tokens = set(re.findall(r'\w{4,}', d.text.lower()))
                        overlap = len(task_tokens.intersection(d_tokens))
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_decision = d
                    if best_overlap > 0:
                        confidence = 0.7
                        rationale = f"Keyword overlap between task and decision"
                    elif len(saved_decisions) == 1:
                        best_decision = saved_decisions[0]
                        confidence = 0.65
                        rationale = "Single primary decision in meeting"

            if best_decision:
                task_model.decision_id = best_decision.id
                if confidence < 0.6:
                    rationale = f"{rationale} (needs confirmation)"

                link_model = Link(
                    source_type="task",
                    source_id=task_model.id,
                    target_type="decision",
                    target_id=best_decision.id,
                    relation=LinkRelation.implements,
                    confirmed=False,
                    confidence=confidence,
                    rationale=rationale,
                )
                db.add(link_model)

        # Mark meeting ready for human review
        meeting.status = MeetingStatus.review
        db.flush()

        audit_log(
            actor=actor,
            action="extract_items",
            entity_type="meeting",
            entity_id=meeting.id,
            before=None,
            after={
                "decisions": len(saved_decisions),
                "actions": len(saved_tasks),
                "dropped_quotes": dropped_quotes_count,
            },
            db=db,
        )

        db.commit()

        premises_count = (
            db.query(Premise)
            .join(Decision, Premise.decision_id == Decision.id)
            .join(Item, Decision.item_id == Item.id)
            .filter(Item.meeting_id == meeting.id)
            .count()
        )

        return {
            "meeting_id": meeting.id,
            "decisions_count": len(saved_decisions),
            "actions_count": len(saved_tasks),
            "premises_count": premises_count,
            "dropped_quotes": dropped_quotes_count,
            "status": meeting.status.value,
        }

    except Exception as e:
        db.rollback()
        meeting.status = MeetingStatus.failed
        meeting.error = str(e)
        db.commit()
        logger.error(f"Extraction failed for meeting {meeting_id}: {e}", exc_info=True)
        raise e
