import json
import logging
import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from rank_bm25 import BM25Okapi

from app.models.models import Meeting, Utterance, Premise, Decision, Alert
from app.models.enums import (
    PremiseState,
    PremiseStatus,
    AlertKind,
    AlertState,
)
from app.llm import complete_json
from app.services.audit import log
from app.services.ledger import scope_overlap

logger = logging.getLogger("decidr.premise_watch")


class PremiseWatchEvaluation(BaseModel):
    premise_id: int
    verdict: Literal["supports", "undermines", "unrelated"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    new_quote: str = ""


class BatchedPremiseWatchOutput(BaseModel):
    evaluations: List[PremiseWatchEvaluation]


STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "are", "was", "were", "be", "this", "that", "it", "with", "as", "by", "from",
    "we", "you", "they", "i", "my", "our", "your", "their", "will", "would", "can",
    "could", "should", "let", "lets", "just", "about", "have", "has", "had", "do",
}


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"\w+", text)]


def _is_exact_substring(needle: str, haystack: str) -> bool:
    """
    Validates that needle is an exact non-empty substring of haystack.
    Invariant 6: Substring verification.
    """
    if not needle or not needle.strip():
        return False
    return needle.strip() in haystack


def watch_meeting_utterances(
    db: Session,
    meeting_id: int,
    actor: str = "premise_watchdog",
) -> List[Alert]:
    """
    Core Novelty: Continuous Premise Watchdog.
    After a meeting is processed, checks EVERY utterance (not just decisions).
    - For each utterance with 5+ words:
      Find candidate premises: confirmed premises with status holding or shaky,
      same project, scope_overlap not disjoint, top 3 by BM25/keyword against the utterance.
    - Runs one batched LLM judge call per utterance with its candidate premises in context.
    - Code decides:
        * 'undermines' with confidence >= 0.7 & valid quote creates a premise_break alert.
        * 'undermines' at 0.4 to 0.7 sets premise status=shaky and creates a possible break alert.
        * 'supports' updates last_supported_at on the premise and creates nothing.
        * 'unrelated' creates nothing.
    - Never requires the linked decision to be mentioned.
    - Invariant 4: Unconfirmed premises are never checked.
    """
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        logger.warning(f"Meeting #{meeting_id} not found for premise watch.")
        return []

    # Retrieve all confirmed premises in same project with status holding or shaky
    # Invariant 4: Unconfirmed premises are NEVER checked
    all_confirmed_premises = (
        db.query(Premise)
        .filter(
            Premise.scope_project == meeting.project,
            Premise.state == PremiseState.confirmed,
            Premise.status.in_([PremiseStatus.holding, PremiseStatus.shaky]),
        )
        .all()
    )

    if not all_confirmed_premises:
        logger.info(f"No active confirmed premises to watch for project '{meeting.project}'.")
        return []

    utterances = (
        db.query(Utterance)
        .filter(Utterance.meeting_id == meeting.id)
        .order_by(Utterance.idx.asc())
        .all()
    )

    meeting_scope = {
        "project": meeting.project,
        "region": meeting.region,
        "release": meeting.release,
    }

    # Filter premises whose scope overlaps with meeting
    eligible_project_premises = [
        p for p in all_confirmed_premises
        if scope_overlap(meeting_scope, p) != "disjoint"
    ]

    if not eligible_project_premises:
        logger.info(f"All confirmed premises in project '{meeting.project}' are disjoint with meeting scope.")
        return []

    created_alerts: List[Alert] = []

    # Build BM25 index over eligible premises
    corpus = [_tokenize(f"{p.text} {p.evidence_quote}") for p in eligible_project_premises]
    bm25 = BM25Okapi(corpus)
    # Apply standard Lucene-style IDF smoothing
    doc_counts: Dict[str, int] = {}
    for doc in corpus:
        for w in set(doc):
            doc_counts[w] = doc_counts.get(w, 0) + 1
    bm25.idf = {
        w: math.log(1.0 + (bm25.corpus_size - f + 0.5) / (f + 0.5))
        for w, f in doc_counts.items()
    }

    for u_idx, utterance in enumerate(utterances):
        words = utterance.text.strip().split()
        if len(words) < 5:
            continue

        u_meaningful = [w for w in _tokenize(f"{utterance.speaker_raw} {utterance.text}") if w not in STOP_WORDS]
        if not u_meaningful:
            continue

        # Score premises against utterance tokens
        scores = bm25.get_scores(u_meaningful)

        # Match named entities, vendor names, numbers, or key words
        candidate_pairs = []
        for p, score in zip(eligible_project_premises, scores):
            p_meaningful = set([w for w in _tokenize(f"{p.text} {p.evidence_quote}") if w not in STOP_WORDS])
            overlap_tokens = set(u_meaningful).intersection(p_meaningful)
            if overlap_tokens:
                total_score = float(score) + (len(overlap_tokens) * 2.0)
                candidate_pairs.append((p, total_score))

        candidate_pairs.sort(key=lambda x: x[1], reverse=True)
        top_candidates = [p for p, _ in candidate_pairs[:3]]

        if not top_candidates:
            continue

        # Build context window with 2 neighbors on each side
        start_i = max(0, u_idx - 2)
        end_i = min(len(utterances), u_idx + 3)
        context_lines = []
        for n in utterances[start_i:end_i]:
            marker = "[FOCAL UTTERANCE] " if n.id == utterance.id else ""
            context_lines.append(f"{marker}{n.speaker_raw}: {n.text}")
        context_window = "\n".join(context_lines)

        candidates_payload = [
            {
                "premise_id": p.id,
                "premise_text": p.text,
                "evidence_quote": p.evidence_quote,
                "scope_region": p.scope_region or "all",
            }
            for p in top_candidates
        ]

        variables = {
            "project": meeting.project,
            "speaker": utterance.speaker_raw,
            "utterance_text": utterance.text,
            "context_window": context_window,
            "candidates_json": json.dumps(candidates_payload, indent=2),
        }

        try:
            judge_res = complete_json(
                prompt_name="watch_premises_batched",
                variables=variables,
                schema=BatchedPremiseWatchOutput,
            )
        except Exception as e:
            logger.warning(f"Premise watch judge call failed for utterance #{utterance.id}: {e}")
            continue

        # Process judge evaluations
        for eval_item in judge_res.evaluations:
            target_premise = db.get(Premise, eval_item.premise_id)
            if not target_premise:
                continue

            verdict = eval_item.verdict
            conf = eval_item.confidence
            new_quote = eval_item.new_quote

            # Substring quote validation (Invariant 6)
            if verdict in ("undermines", "supports"):
                if not _is_exact_substring(new_quote, utterance.text):
                    logger.warning(
                        f"Dropping premise watch quote hallucination: '{new_quote}' not in utterance #{utterance.id} "
                        f"('{utterance.text}')."
                    )
                    continue

            if verdict == "undermines" and conf >= 0.7:
                # High-confidence premise break alert
                # Premise becomes broken ONLY when human confirms the alert!
                alert = Alert(
                    kind=AlertKind.premise_break,
                    meeting_id=meeting.id,
                    utterance_id=utterance.id,
                    premise_id=target_premise.id,
                    decision_id=target_premise.decision_id,
                    verdict="premise_break",
                    old_quote=target_premise.evidence_quote,
                    new_quote=new_quote,
                    explanation=f"Speaker: {utterance.speaker_raw}. {eval_item.explanation}",
                    state=AlertState.open,
                )
                db.add(alert)
                db.flush()

                log(
                    actor=actor,
                    action="create_premise_break_alert",
                    entity_type="alert",
                    entity_id=alert.id,
                    before=None,
                    after={
                        "premise_id": target_premise.id,
                        "utterance_id": utterance.id,
                        "confidence": conf,
                        "speaker": utterance.speaker_raw,
                    },
                    db=db,
                )
                created_alerts.append(alert)

            elif verdict == "undermines" and 0.4 <= conf < 0.7:
                # Ambiguous / moderate undermines: set status to shaky and create confirmation card
                prev_st = target_premise.status.value
                target_premise.status = PremiseStatus.shaky

                alert = Alert(
                    kind=AlertKind.premise_break,
                    meeting_id=meeting.id,
                    utterance_id=utterance.id,
                    premise_id=target_premise.id,
                    decision_id=target_premise.decision_id,
                    verdict="possible_break_please_confirm",
                    old_quote=target_premise.evidence_quote,
                    new_quote=new_quote,
                    explanation=f"[Possible break, please confirm] Speaker: {utterance.speaker_raw}. {eval_item.explanation}",
                    state=AlertState.open,
                )
                db.add(alert)
                db.flush()

                log(
                    actor=actor,
                    action="mark_premise_shaky",
                    entity_type="premise",
                    entity_id=target_premise.id,
                    before={"status": prev_st},
                    after={"status": target_premise.status.value, "confidence": conf},
                    db=db,
                )
                created_alerts.append(alert)

            elif verdict == "supports":
                # Premise re-affirmed: update last_supported_at and create nothing
                target_premise.last_supported_at = datetime.now(timezone.utc)
                log(
                    actor=actor,
                    action="support_premise",
                    entity_type="premise",
                    entity_id=target_premise.id,
                    before=None,
                    after={
                        "last_supported_at": target_premise.last_supported_at.isoformat(),
                        "speaker": utterance.speaker_raw,
                    },
                    db=db,
                )

    db.commit()
    return created_alerts


def run_expiry(
    db: Session,
    as_of: Optional[date] = None,
    actor: str = "expiry_scheduler",
) -> List[Alert]:
    """
    Evaluates premise validity dates:
    - Marks premises with valid_until < as_of as 'expired' and creates an expiry alert.
    - Premises within 7 days of valid_until become 'shaky'.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc).date()

    candidates = (
        db.query(Premise)
        .filter(
            Premise.state == PremiseState.confirmed,
            Premise.valid_until.isnot(None),
            Premise.status != PremiseStatus.expired,
        )
        .all()
    )

    created_alerts: List[Alert] = []
    shaky_horizon = as_of + timedelta(days=7)

    for p in candidates:
        if p.valid_until < as_of:
            # Expired
            prev_status = p.status.value
            p.status = PremiseStatus.expired

            alert = Alert(
                kind=AlertKind.expiry,
                premise_id=p.id,
                decision_id=p.decision_id,
                verdict="premise_expired",
                old_quote=p.evidence_quote,
                explanation=f"Premise expired on {p.valid_until.isoformat()} (evaluated as of {as_of.isoformat()}).",
                state=AlertState.open,
            )
            db.add(alert)
            db.flush()

            log(
                actor=actor,
                action="expire_premise",
                entity_type="premise",
                entity_id=p.id,
                before={"status": prev_status},
                after={
                    "status": p.status.value,
                    "valid_until": p.valid_until.isoformat(),
                    "as_of": as_of.isoformat(),
                },
                db=db,
            )
            created_alerts.append(alert)

        elif as_of <= p.valid_until <= shaky_horizon:
            # Within 7 days of valid_until: becomes shaky
            if p.status == PremiseStatus.holding:
                prev_status = p.status.value
                p.status = PremiseStatus.shaky

                log(
                    actor=actor,
                    action="mark_premise_shaky_nearing_expiry",
                    entity_type="premise",
                    entity_id=p.id,
                    before={"status": prev_status},
                    after={
                        "status": p.status.value,
                        "valid_until": p.valid_until.isoformat(),
                        "as_of": as_of.isoformat(),
                    },
                    db=db,
                )

    db.commit()
    return created_alerts
