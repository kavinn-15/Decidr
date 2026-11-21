import uuid
from datetime import date, datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, engine, Base, init_db
from app.models.models import (
    Person,
    Meeting,
    Utterance,
    Item,
    Decision,
    Premise,
    Alert,
)
from app.models.enums import (
    MeetingStatus,
    ItemType,
    ReviewState,
    DecisionStatus,
    PremiseState,
    PremiseStatus,
    AlertKind,
    AlertState,
)
from app.llm.adapter import adapter
from app.services.premise_watch import watch_meeting_utterances
from app.services.conflicts import detect_conflicts_for_decision


@pytest.fixture
def db_session():
    init_db(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def configure_llm_mode():
    orig_provider = settings.LLM_PROVIDER
    orig_mode = settings.LLM_MODE
    settings.LLM_PROVIDER = "fake"
    settings.LLM_MODE = "live"
    adapter.fake_queue.clear()
    yield
    settings.LLM_PROVIDER = orig_provider
    settings.LLM_MODE = orig_mode
    adapter.fake_queue.clear()


@pytest.fixture
def fp_setup(db_session: Session):
    """
    Setup 15 Edge-Case / False-Positive Protection Test Environment.
    Decision D1: Use Provider A for India UPI payments.
    Confirmed Premise P1: Provider A supports T+0 UPI settlement in India.
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Payments Platform {uid}"

    person = Person(
        name=f"Lead Architect {uid}",
        email=f"lead_{uid}@example.com",
        tracker_id=f"LEAD-{uid}",
    )
    db_session.add(person)
    db_session.flush()

    m1 = Meeting(
        title=f"Initial Architecture {uid}",
        date=date(2026, 11, 2),
        project=project,
        region="India",
        transcript_ref="seed/m1.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(m1)
    db_session.flush()

    item_d1 = Item(
        meeting_id=m1.id,
        type=ItemType.decision,
        text="Use Provider A for India UPI payments",
        evidence_quote="Provider A for India UPI payments",
        review_state=ReviewState.approved,
    )
    db_session.add(item_d1)
    db_session.flush()

    d1 = Decision(
        item_id=item_d1.id,
        text="Use Provider A for India UPI payments",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d1)
    db_session.flush()

    p1 = Premise(
        decision_id=d1.id,
        text="Provider A supports T+0 UPI settlement in India",
        evidence_quote="Provider A supports T+0 UPI settlement in India",
        scope_project=project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
        valid_until=date(2026, 12, 31),
    )
    db_session.add(p1)
    db_session.commit()

    return {
        "project": project,
        "person": person,
        "m1": m1,
        "d1": d1,
        "p1": p1,
    }


def _create_meeting_with_utterance(
    db: Session,
    project: str,
    region: str,
    speaker: str,
    text: str,
    meeting_title: str = "Sync",
) -> Tuple[Meeting, Utterance]:
    m = Meeting(
        title=meeting_title,
        date=date(2026, 11, 10),
        project=project,
        region=region,
        transcript_ref="seed/test_sync.vtt",
        status=MeetingStatus.done,
    )
    db.add(m)
    db.flush()
    u = Utterance(
        meeting_id=m.id,
        idx=0,
        speaker_raw=speaker,
        text=text,
    )
    db.add(u)
    db.commit()
    return m, u


from typing import Tuple


def test_case_a_same_vendor_different_country(db_session: Session, fp_setup):
    """
    Case A: Same vendor, different country.
    'Provider A in Europe only does T+2' when premise was 'Provider A in India does T+0'.
    Assert: NO ALERT (scope disjoint India vs Europe).
    """
    project = fp_setup["project"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="Europe",
        speaker="Divya",
        text="Provider A in Europe only does T+2 settlement for all SEPA transfers.",
    )
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_b_same_feature_different_project(db_session: Session, fp_setup):
    """
    Case B: Same feature, different project.
    'Provider A only does T+2 settlement' in Project Alpha.
    Assert: NO ALERT for P1 (different project scope).
    """
    m, _ = _create_meeting_with_utterance(
        db_session,
        project="Unrelated Project Alpha",
        region="India",
        speaker="Kavita",
        text="Provider A only does T+2 settlement for this specific platform.",
    )
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_c_same_premise_different_time_period(db_session: Session, fp_setup):
    """
    Case C: Same premise, different time period.
    'Provider A had T+2 back in 2024' when premise is for 2026.
    Assert: NO ALERT (LLM classifies historical fact as unrelated).
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Vikram",
        text="Provider A had T+2 back in 2024 during their legacy pilot launch.",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "unrelated",
            "confidence": 0.90,
            "explanation": "Refers to historical 2024 status, not current 2026 capabilities.",
            "new_quote": "Provider A had T+2 back in 2024",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_d_limitation_resolved(db_session: Session, fp_setup):
    """
    Case D: Limitation resolved.
    'Provider A confirmed they resolved the gateway glitch and now reliably support T+0.'
    Assert: NO ALERT (verdict supports updates last_supported_at).
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Asha",
        text="Provider A confirmed they resolved the gateway glitch and now reliably support T+0 in India.",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "supports",
            "confidence": 0.98,
            "explanation": "Confirms provider supports T+0 after resolving glitch.",
            "new_quote": "reliably support T+0 in India",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0
    db_session.refresh(p1)
    assert p1.last_supported_at is not None


def test_case_e_question_rather_than_fact(db_session: Session, fp_setup):
    """
    Case E: Question rather than fact.
    'Does Provider A support T+2 settlement or is it T+0?'
    Assert: NO ALERT (a question is not a factual invalidation).
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Rohan",
        text="Does Provider A support T+2 settlement or is it T+0 for UPI in India?",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "unrelated",
            "confidence": 0.95,
            "explanation": "Speaker is asking an open question, not asserting a fact.",
            "new_quote": "",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_f_hypothetical_statement(db_session: Session, fp_setup):
    """
    Case F: Hypothetical statement.
    'If Provider A were to drop to T+2, what would our contingency plan be?'
    Assert: NO ALERT.
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Ananya",
        text="If Provider A were to drop to T+2, what would our contingency plan be for reconciliation?",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "unrelated",
            "confidence": 0.92,
            "explanation": "Hypothetical question exploring a scenario, not a factual update.",
            "new_quote": "",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_g_premise_remains_true(db_session: Session, fp_setup):
    """
    Case G: Premise remains true.
    'Provider A continues to provide T+0 settlement without issues.'
    Assert: NO ALERT; updates last_supported_at.
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Karthik",
        text="Provider A continues to provide T+0 settlement without issues across all merchant flows.",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "supports",
            "confidence": 0.99,
            "explanation": "Affirms continuous operation of T+0 UPI settlements.",
            "new_quote": "continues to provide T+0 settlement without issues",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0
    db_session.refresh(p1)
    assert p1.last_supported_at is not None


def test_case_h_explicit_decision_reversal_creates_conflict_alert(db_session: Session, fp_setup):
    """
    Case H: Explicit decision reversal.
    'We are switching from Provider A to Provider B for India payments'
    Assert: CONFLICT ALERT (supersedes), NOT silent premise break.
    """
    project = fp_setup["project"]
    d1 = fp_setup["d1"]

    # New decision item
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Asha",
        text="We are switching from Provider A to Provider B for India payments.",
    )
    item_reversal = Item(
        meeting_id=m.id,
        type=ItemType.decision,
        text="Switch from Provider A to Provider B for India payments",
        evidence_quote="switching from Provider A to Provider B",
        review_state=ReviewState.approved,
    )
    db_session.add(item_reversal)
    db_session.flush()

    d_reversal = Decision(
        item_id=item_reversal.id,
        text="Switch from Provider A to Provider B for India payments",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d_reversal)
    db_session.commit()

    adapter.enqueue_fake_response({
        "verdict": "supersedes",
        "confidence": 0.96,
        "explanation": "Decision explicitly reverses vendor selection from Provider A to Provider B.",
        "old_quote": "Provider A",
        "new_quote": "Provider B",
    })

    conflict_alerts = detect_conflicts_for_decision(db_session, d_reversal)
    assert len(conflict_alerts) == 1
    assert conflict_alerts[0].kind == AlertKind.conflict
    assert conflict_alerts[0].verdict == "supersedes"


def test_case_i_silent_premise_invalidation(db_session: Session, fp_setup):
    """
    Case I: Silent premise invalidation.
    'Provider A's API docs say settlement is T+2' with NO mention of Decision 1.
    Assert: PREMISE BREAK ALERT created on P1!
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Sam",
        text="Provider A's API docs say settlement is T+2 for all production endpoints.",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "undermines",
            "confidence": 0.94,
            "explanation": "API documentation specifies T+2 settlement, directly breaking the T+0 premise.",
            "new_quote": "settlement is T+2",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 1
    assert alerts[0].kind == AlertKind.premise_break
    assert alerts[0].premise_id == p1.id
    assert alerts[0].new_quote == "settlement is T+2"


def test_case_j_substring_hallucination_dropped(db_session: Session, fp_setup):
    """
    Case J: Substring hallucination dropped.
    LLM returns a quote not present in the utterance.
    Assert: Invariant 6 drops the alert completely.
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Sam",
        text="Provider A's settlement window is now T+2.",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "undermines",
            "confidence": 0.95,
            "explanation": "Fabricated quote test",
            "new_quote": "COMPLETELY FABRICATED QUOTE NOT IN UTTERANCE",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_k_low_confidence_undermine_dropped(db_session: Session, fp_setup):
    """
    Case K: Low confidence undermine (confidence < 0.4).
    Assert: NO ALERT; premise remains holding.
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Sam",
        text="Provider A has some delays occasionally.",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "undermines",
            "confidence": 0.25,
            "explanation": "Weak speculation",
            "new_quote": "delays occasionally",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0
    db_session.refresh(p1)
    assert p1.status == PremiseStatus.holding


def test_case_l_medium_confidence_creates_shaky_alert(db_session: Session, fp_setup):
    """
    Case L: Medium confidence undermine (0.4 <= confidence < 0.7).
    Assert: Shaky alert created, premise status updated to shaky.
    """
    project = fp_setup["project"]
    p1 = fp_setup["p1"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Sam",
        text="Provider A might have changed their settlement tier to T+2.",
    )
    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p1.id,
            "verdict": "undermines",
            "confidence": 0.55,
            "explanation": "Possible break, needs confirmation",
            "new_quote": "might have changed their settlement tier to T+2",
        }]
    })
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 1
    assert alerts[0].kind == AlertKind.premise_break
    assert "Possible break" in alerts[0].explanation
    db_session.refresh(p1)
    assert p1.status == PremiseStatus.shaky


def test_case_m_short_utterance_skipped(db_session: Session, fp_setup):
    """
    Case M: Short utterance (< 5 words).
    Assert: Premise watch skips without LLM call.
    """
    project = fp_setup["project"]
    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Sam",
        text="T+2 is slow.",
    )
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_n_unconfirmed_premise_skipped(db_session: Session, fp_setup):
    """
    Case N: Unconfirmed premise (state=proposed) in same project.
    Assert: Invariant 4 - completely excluded from watchdog index.
    """
    project = fp_setup["project"]
    d1 = fp_setup["d1"]

    p_unconfirmed = Premise(
        decision_id=d1.id,
        text="Provider A charges zero onboarding fees",
        evidence_quote="charges zero onboarding fees",
        scope_project=project,
        scope_region="India",
        state=PremiseState.proposed,  # unconfirmed!
        status=PremiseStatus.holding,
    )
    db_session.add(p_unconfirmed)
    db_session.commit()

    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Sam",
        text="Provider A charges zero onboarding fees is completely incorrect.",
    )
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_case_o_expired_premise_skipped(db_session: Session, fp_setup):
    """
    Case O: Expired premise in same project.
    Assert: Premise watchdog ignores already-expired premises.
    """
    project = fp_setup["project"]
    d1 = fp_setup["d1"]

    p_expired = Premise(
        decision_id=d1.id,
        text="Beta sandbox access valid until yesterday",
        evidence_quote="Beta sandbox access",
        scope_project=project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.expired,  # expired!
        valid_until=date(2026, 11, 1),
    )
    db_session.add(p_expired)
    db_session.commit()

    m, _ = _create_meeting_with_utterance(
        db_session,
        project=project,
        region="India",
        speaker="Sam",
        text="Beta sandbox access is now completely shut down.",
    )
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0
