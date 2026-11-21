import uuid
from datetime import date, datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, init_db, engine
from app.models.models import (
    Person,
    Meeting,
    Utterance,
    Item,
    Decision,
    Premise,
    Task,
    Link,
    Alert,
    TrackerTicket,
    ChangeProposal,
)
from app.models.enums import (
    MeetingStatus,
    ItemType,
    ReviewState,
    DecisionStatus,
    PremiseState,
    PremiseStatus,
    LinkRelation,
    TaskStatus,
    AlertKind,
    AlertState,
    ProposalState,
    ActionType,
)
from app.llm.adapter import adapter
from app.services.premise_watch import watch_meeting_utterances
from app.services.blast_radius import calculate_blast_radius
from app.services.repair import generate_repair_plan


@pytest.fixture
def db():
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


def test_phase2_complete_scenario_meeting1_and_meeting2(db: Session):
    """
    Phase 2 Core Scenario:
    MEETING 1:
    "We selected Vendor A because it supports international recurring payments."
    Decision: Use Vendor A for recurring payments.
    Premise: Vendor A supports international recurring payments.

    MEETING 2:
    "Vendor A informed us that international recurring payments are not supported."
    Nobody explicitly refers to the earlier decision.

    Expected behavior:
    1. Detect the new statement.
    2. Find the old confirmed premise.
    3. Recognize that the new statement undermines it.
    4. Display both quotations and timestamps.
    5. Identify the original decision.
    6. Find all dependent tasks (direct + multi-hop).
    7. Explain why each task is affected.
    8. Prepare an appropriate repair plan.
    9. Wait for human approval (state draft, 0 external writes).
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Global Subscriptions {uid}"

    lead = Person(name="Lead Dev", email=f"lead_{uid}@example.com", tracker_id=f"LEAD-{uid}")
    db.add(lead)
    db.flush()

    # --- MEETING 1 ---
    m1 = Meeting(
        title="Vendor Selection Kickoff",
        date=date(2026, 11, 2),
        project=project,
        transcript_ref="seed/m1.vtt",
        status=MeetingStatus.done,
    )
    db.add(m1)
    db.flush()

    u1_m1 = Utterance(
        meeting_id=m1.id,
        idx=0,
        speaker_raw="Asha",
        person_id=lead.id,
        text="We selected Vendor A because it supports international recurring payments.",
        start_ts=70.0,
    )
    db.add(u1_m1)
    db.flush()

    item_d1 = Item(
        meeting_id=m1.id,
        type=ItemType.decision,
        text="Use Vendor A for recurring payments",
        evidence_quote="We selected Vendor A because it supports international recurring payments.",
        utterance_id=u1_m1.id,
        review_state=ReviewState.approved,
    )
    db.add(item_d1)
    db.flush()

    d1 = Decision(
        item_id=item_d1.id,
        text="Use Vendor A for recurring payments",
        scope_project=project,
        status=DecisionStatus.active,
        version=1,
    )
    db.add(d1)
    db.flush()

    p1 = Premise(
        decision_id=d1.id,
        text="Vendor A supports international recurring payments",
        evidence_quote="supports international recurring payments",
        utterance_id=u1_m1.id,
        scope_project=project,
        state=PremiseState.confirmed,  # Confirmed by human
        status=PremiseStatus.holding,
        confidence=0.98,
    )
    db.add(p1)
    db.flush()

    # Task T1: Direct implementation of D1
    t1_item = Item(
        meeting_id=m1.id,
        type=ItemType.action,
        text="Integrate Vendor A recurring billing SDK",
        evidence_quote="Integrate Vendor A",
        review_state=ReviewState.approved,
    )
    db.add(t1_item)
    db.flush()

    t1 = Task(
        item_id=t1_item.id,
        decision_id=d1.id,
        title="Integrate Vendor A recurring billing SDK",
        estimate_hours=16.0,
        status=TaskStatus.open,
        tracker_ref=f"TICK-{uid}-1",
    )
    db.add(t1)
    db.flush()

    link_t1_d1 = Link(
        source_type="task",
        source_id=t1.id,
        target_type="decision",
        target_id=d1.id,
        relation=LinkRelation.implements,
        confirmed=True,
    )
    db.add(link_t1_d1)

    # Dependent Decision D2: depends_on D1 (2-hop dependency)
    item_d2 = Item(
        meeting_id=m1.id,
        type=ItemType.decision,
        text="Launch multi-currency subscription tiers",
        evidence_quote="Launch multi-currency tiers",
        review_state=ReviewState.approved,
    )
    db.add(item_d2)
    db.flush()

    d2 = Decision(
        item_id=item_d2.id,
        text="Launch multi-currency subscription tiers",
        scope_project=project,
        status=DecisionStatus.active,
        version=1,
    )
    db.add(d2)
    db.flush()

    link_d2_d1 = Link(
        source_type="decision",
        source_id=d2.id,
        target_type="decision",
        target_id=d1.id,
        relation=LinkRelation.depends_on,
        confirmed=True,
    )
    db.add(link_d2_d1)

    # Task T2: Implements D2 (indirect dependency from D1 / P1)
    t2_item = Item(
        meeting_id=m1.id,
        type=ItemType.action,
        text="Configure multi-currency recurring plans",
        evidence_quote="Configure multi-currency",
        review_state=ReviewState.approved,
    )
    db.add(t2_item)
    db.flush()

    t2 = Task(
        item_id=t2_item.id,
        decision_id=d2.id,
        title="Configure multi-currency recurring plans",
        estimate_hours=24.0,
        status=TaskStatus.open,
        tracker_ref=f"TICK-{uid}-2",
    )
    db.add(t2)
    db.flush()

    link_t2_d2 = Link(
        source_type="task",
        source_id=t2.id,
        target_type="decision",
        target_id=d2.id,
        relation=LinkRelation.implements,
        confirmed=True,
    )
    db.add(link_t2_d2)
    db.commit()

    # --- MEETING 2 ---
    m2 = Meeting(
        title="Vendor SLA Follow-up",
        date=date(2026, 11, 9),
        project=project,
        transcript_ref="seed/m2.vtt",
        status=MeetingStatus.done,
    )
    db.add(m2)
    db.flush()

    # Utterance in Meeting 2 with NO mention of Decision 1
    u_m2 = Utterance(
        meeting_id=m2.id,
        idx=0,
        speaker_raw="Sam",
        text="Vendor A informed us that international recurring payments are not supported.",
        start_ts=262.0,
    )
    db.add(u_m2)
    db.commit()

    # Enqueue fake LLM judge evaluation
    adapter.enqueue_fake_response({
        "evaluations": [
            {
                "premise_id": p1.id,
                "verdict": "undermines",
                "confidence": 0.95,
                "explanation": "Vendor A explicitly stated that international recurring payments are not supported.",
                "new_quote": "international recurring payments are not supported",
            }
        ]
    })

    # 1. Continuous Watchdog detects the new statement
    alerts = watch_meeting_utterances(db, m2.id)
    assert len(alerts) == 1
    alert = alerts[0]

    # 2. Find old confirmed premise
    assert alert.premise_id == p1.id
    # 3. Recognize that new statement undermines it
    assert alert.kind == AlertKind.premise_break
    assert alert.verdict == "premise_break"

    # 4. Display both quotations and timestamps
    assert alert.old_quote == "supports international recurring payments"
    assert alert.new_quote == "international recurring payments are not supported"
    assert alert.utterance_id == u_m2.id
    assert u_m2.start_ts == 262.0
    assert u1_m1.start_ts == 70.0

    # 5. Identify original decision
    assert alert.decision_id == d1.id

    # 6. Find all dependent tasks (direct T1 and multi-hop T2)
    blast = calculate_blast_radius(db, alert_id=alert.id)
    affected_ids = {t["id"] for t in blast["affected"]}
    assert t1.id in affected_ids
    assert t2.id in affected_ids

    # 7. Explain why each task is affected
    t1_info = next(t for t in blast["affected"] if t["id"] == t1.id)
    t2_info = next(t for t in blast["affected"] if t["id"] == t2.id)
    assert t1_info["depth"] == 1
    assert "justifies T" in t1_info["reason"]
    assert t2_info["depth"] == 2
    assert "depends on" in t2_info["reason"]

    tickets_before = db.query(TrackerTicket).count()

    # 8. Prepare an appropriate repair plan
    proposal = generate_repair_plan(db, alert_id=alert.id, suggest_replacements=False)
    assert proposal is not None
    assert len(proposal.actions) >= 3

    action_types = {a.action_type for a in proposal.actions}
    assert ActionType.mark_decision_at_risk in action_types
    assert ActionType.comment_task in action_types
    assert ActionType.pause_reminders in action_types

    # 9. Wait for human approval (state draft, 0 external writes)
    assert proposal.state == ProposalState.draft
    # Verify ZERO new writes to tracker tickets occurred
    tickets_after = db.query(TrackerTicket).count()
    assert tickets_after == tickets_before


def test_four_verdicts_handling_in_watchdog(db: Session):
    """
    Test Phase 2:
    Support four verdicts:
    - SUPPORTS
    - UNDERMINES
    - UNRELATED
    - UNCERTAIN
    Never treat uncertain evidence as a confirmed premise break.
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Verdict Test {uid}"

    m = Meeting(
        title="Architecture Sync",
        date=date(2026, 11, 2),
        project=project,
        region="India",
        transcript_ref="seed/test.vtt",
        status=MeetingStatus.done,
    )
    db.add(m)
    db.flush()

    item_d = Item(
        meeting_id=m.id,
        type=ItemType.decision,
        text="Use PostgreSQL for primary store",
        evidence_quote="PostgreSQL for primary store",
        review_state=ReviewState.approved,
    )
    db.add(item_d)
    db.flush()

    d = Decision(
        item_id=item_d.id,
        text="Use PostgreSQL for primary store",
        scope_project=project,
        status=DecisionStatus.active,
        version=1,
    )
    db.add(d)
    db.flush()

    p = Premise(
        decision_id=d.id,
        text="PostgreSQL supports multi-region read replicas with low replication lag",
        evidence_quote="multi-region read replicas",
        scope_project=project,
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
        confidence=1.0,
    )
    db.add(p)
    db.commit()

    # 1. SUPPORTS verdict
    m_sup = Meeting(
        title="Benchmark Sync",
        date=date(2026, 11, 3),
        project=project,
        region="India",
        transcript_ref="seed/test_sup.vtt",
        status=MeetingStatus.done,
    )
    db.add(m_sup)
    db.flush()
    u_supports = Utterance(
        meeting_id=m_sup.id,
        idx=0,
        speaker_raw="Dev",
        text="Benchmark results confirm PostgreSQL read replicas have under 50ms latency.",
    )
    db.add(u_supports)
    db.commit()

    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p.id,
            "verdict": "supports",
            "confidence": 0.96,
            "explanation": "Affirms low latency replica support.",
            "new_quote": "PostgreSQL read replicas have under 50ms latency",
        }]
    })
    alerts_sup = watch_meeting_utterances(db, m_sup.id)
    assert len(alerts_sup) == 0
    db.refresh(p)
    assert p.last_supported_at is not None
    assert p.status == PremiseStatus.holding

    # 2. UNCERTAIN verdict
    m_unc = Meeting(
        title="Ops Rumor Sync",
        date=date(2026, 11, 4),
        project=project,
        region="India",
        transcript_ref="seed/test_unc.vtt",
        status=MeetingStatus.done,
    )
    db.add(m_unc)
    db.flush()
    u_uncertain = Utterance(
        meeting_id=m_unc.id,
        idx=0,
        speaker_raw="Ops",
        text="I heard someone say PostgreSQL cross-region replication might have higher lag than expected.",
    )
    db.add(u_uncertain)
    db.commit()

    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p.id,
            "verdict": "uncertain",
            "confidence": 0.60,
            "explanation": "Unverified rumor about replication lag.",
            "new_quote": "might have higher lag than expected",
        }]
    })
    alerts_unc = watch_meeting_utterances(db, m_unc.id)
    assert len(alerts_unc) == 1
    # NEVER treat as confirmed premise break
    assert alerts_unc[0].verdict == "possible_break_please_confirm"
    assert "[Uncertain evidence, please confirm]" in alerts_unc[0].explanation
    db.refresh(p)
    # Status becomes shaky, NEVER broken!
    assert p.status == PremiseStatus.shaky

    # 3. UNRELATED verdict (mentions PostgreSQL but factually unrelated to replicas)
    m_unrel = Meeting(
        title="Design Sync",
        date=date(2026, 11, 5),
        project=project,
        region="India",
        transcript_ref="seed/test_unrel.vtt",
        status=MeetingStatus.done,
    )
    db.add(m_unrel)
    db.flush()
    u_unrelated = Utterance(
        meeting_id=m_unrel.id,
        idx=0,
        speaker_raw="Frontend",
        text="We finished redesigning the PostgreSQL admin console button hover states.",
    )
    db.add(u_unrelated)
    db.commit()

    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p.id,
            "verdict": "unrelated",
            "confidence": 0.99,
            "explanation": "Discussion of CSS buttons has no bearing on database replicas.",
            "new_quote": "",
        }]
    })
    alerts_unrel = watch_meeting_utterances(db, m_unrel.id)
    assert len(alerts_unrel) == 0

    # 4. UNDERMINES verdict (High Confidence)
    m_und = Meeting(
        title="DBA Review",
        date=date(2026, 11, 6),
        project=project,
        region="India",
        transcript_ref="seed/test_und.vtt",
        status=MeetingStatus.done,
    )
    db.add(m_und)
    db.flush()
    u_undermines = Utterance(
        meeting_id=m_und.id,
        idx=0,
        speaker_raw="DBA",
        text="Managed PostgreSQL provider does not support multi-region replication in our tier.",
    )
    db.add(u_undermines)
    db.commit()

    adapter.enqueue_fake_response({
        "evaluations": [{
            "premise_id": p.id,
            "verdict": "undermines",
            "confidence": 0.95,
            "explanation": "Provider tier lacks multi-region replication, directly contradicting premise.",
            "new_quote": "does not support multi-region replication",
        }]
    })
    alerts_und = watch_meeting_utterances(db, m_und.id)
    assert len(alerts_und) == 1
    assert alerts_und[0].verdict == "premise_break"
    assert alerts_und[0].kind == AlertKind.premise_break
