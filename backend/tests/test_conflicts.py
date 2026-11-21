import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, engine, Base
from app.models.models import (
    Person,
    Meeting,
    Item,
    Decision,
    Task,
    Alert,
    Link,
    AuditLog,
)
from app.models.enums import (
    MeetingStatus,
    ItemType,
    ReviewState,
    DecisionStatus,
    AlertKind,
    AlertState,
    LinkRelation,
    TaskStatus,
)
from app.llm.adapter import adapter
from app.services.conflicts import (
    detect_conflicts_for_decision,
    approve_supersedes_alert,
    notify_blast_radius_service,
)
from app.services.links import neighbors


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
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
def test_setup(db_session: Session):
    uid = uuid.uuid4().hex[:6]
    project = f"Payments Revamp {uid}"

    person = Person(
        name=f"Ravi {uid}",
        email=f"ravi_{uid}@example.com",
        tracker_id=f"TRK-{uid}",
    )
    db_session.add(person)
    db_session.flush()

    meeting = Meeting(
        title=f"Kickoff {uid}",
        date=date(2026, 11, 2),
        project=project,
        region="India",
        transcript_ref="seed/m1.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(meeting)
    db_session.flush()

    # D1: Provider A for India
    item1 = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Use Provider A for India settlements",
        evidence_quote="Provider A for India settlements",
        review_state=ReviewState.approved,
    )
    db_session.add(item1)
    db_session.flush()

    d1 = Decision(
        item_id=item1.id,
        text="Use Provider A for India settlements",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d1)

    # D2: Launch India payments on Dec 15
    item2 = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Launch India payments on Dec 15",
        evidence_quote="Launch India payments on Dec 15",
        review_state=ReviewState.approved,
    )
    db_session.add(item2)
    db_session.flush()

    d2 = Decision(
        item_id=item2.id,
        text="Launch India payments on Dec 15",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d2)
    db_session.flush()

    # Open task linked to D2
    item_task = Item(
        meeting_id=meeting.id,
        type=ItemType.action,
        text="Prepare India launch checklist",
        evidence_quote="launch checklist",
        review_state=ReviewState.approved,
    )
    db_session.add(item_task)
    db_session.flush()

    task_d2 = Task(
        item_id=item_task.id,
        decision_id=d2.id,
        title="Prepare India launch checklist",
        owner_id=person.id,
        status=TaskStatus.open,
    )
    db_session.add(task_d2)

    db_session.commit()

    return {
        "project": project,
        "meeting": meeting,
        "person": person,
        "d1": d1,
        "d2": d2,
        "task_d2": task_d2,
    }


def test_europe_decision_vs_d1_yields_no_alert_and_zero_llm_calls(db_session: Session, test_setup):
    """
    Test: The M2 Europe decision vs D1 yields no alert and makes 0 LLM calls.
    Scope disjointness (India vs Europe) must skip LLM judge entirely.
    """
    project = test_setup["project"]
    meeting = test_setup["meeting"]

    # M2 Europe decision: region is Europe
    item_europe = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Evaluate Provider B for Europe payments",
        evidence_quote="Provider B for Europe payments",
        review_state=ReviewState.approved,
    )
    db_session.add(item_europe)
    db_session.flush()

    d_europe = Decision(
        item_id=item_europe.id,
        text="Evaluate Provider B for Europe payments",
        scope_project=project,
        scope_region="Europe",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d_europe)
    db_session.commit()

    # Spy on complete_json to verify exactly 0 calls are made
    with patch("app.services.conflicts.complete_json") as mock_complete:
        alerts = detect_conflicts_for_decision(db_session, d_europe)

        # Must create no alerts
        assert len(alerts) == 0
        # Must make ZERO LLM calls because scope is disjoint (India vs Europe)
        assert mock_complete.call_count == 0


def test_m3_launch_date_change_yields_supersedes_alert_against_d2(db_session: Session, test_setup):
    """
    Test: The M3 launch-date change yields a supersedes alert against D2.
    Approving the supersedes alert:
    - Sets D2 status=superseded
    - Creates confirmed supersedes link
    - Marks its linked open tasks at_risk
    """
    project = test_setup["project"]
    meeting = test_setup["meeting"]
    d2 = test_setup["d2"]
    task_d2 = test_setup["task_d2"]

    # M3 decision: Move India launch to Jan 15 (same project, same region India)
    item_m3 = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Move India launch to Jan 15",
        evidence_quote="Move India launch to Jan 15",
        review_state=ReviewState.approved,
    )
    db_session.add(item_m3)
    db_session.flush()

    d_m3 = Decision(
        item_id=item_m3.id,
        text="Move India launch to Jan 15",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d_m3)
    db_session.commit()

    # Enqueue fake LLM response for judge_decision_conflict
    adapter.enqueue_fake_response({
        "verdict": "supersedes",
        "confidence": 0.95,
        "explanation": "The launch date has been officially moved from Dec 15 to Jan 15.",
        "old_quote": "Dec 15",
        "new_quote": "Jan 15",
    })

    alerts = detect_conflicts_for_decision(db_session, d_m3, actor="reviewer_bob")
    db_session.commit()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.kind == AlertKind.conflict
    assert alert.verdict == "supersedes"
    assert alert.decision_id == d_m3.id
    assert alert.old_quote == "Dec 15"
    assert alert.new_quote == "Jan 15"
    assert alert.state == AlertState.open

    # Now approve the supersedes alert
    confirmed_alert = approve_supersedes_alert(db_session, alert.id, actor="reviewer_carol")
    db_session.commit()

    assert confirmed_alert.state == AlertState.confirmed

    # 1. Old decision (D2) must now be superseded
    db_session.refresh(d2)
    assert d2.status == DecisionStatus.superseded
    assert d_m3.supersedes_id == d2.id

    # 2. Confirmed supersedes link must exist in the knowledge graph
    graph_links = neighbors(db_session, ("decision", d_m3.id), relations=[LinkRelation.supersedes], confirmed_only=True)
    assert len(graph_links) == 1
    assert graph_links[0]["node_id"] == d2.id
    assert graph_links[0]["relation"] == "supersedes"
    assert graph_links[0]["confirmed"] is True

    # 3. Linked open tasks of D2 must now be marked at_risk
    db_session.refresh(task_d2)
    assert task_d2.status == TaskStatus.at_risk


def test_consistent_decisions_yield_nothing(db_session: Session, test_setup):
    """
    Test: Consistent decisions yield nothing (0 alerts created).
    """
    project = test_setup["project"]
    meeting = test_setup["meeting"]

    item_cons = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Setup monitoring dashboard for settlements",
        evidence_quote="monitoring dashboard for settlements",
        review_state=ReviewState.approved,
    )
    db_session.add(item_cons)
    db_session.flush()

    d_cons = Decision(
        item_id=item_cons.id,
        text="Setup monitoring dashboard for settlements",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d_cons)
    db_session.commit()

    # Enqueue fake response with consistent verdict
    adapter.enqueue_fake_response({
        "verdict": "consistent",
        "confidence": 0.90,
        "explanation": "Monitoring is complementary to provider integration.",
        "old_quote": "India settlements",
        "new_quote": "settlements",
    })

    alerts = detect_conflicts_for_decision(db_session, d_cons)
    assert len(alerts) == 0


def test_quote_verification_rejects_hallucinations(db_session: Session, test_setup):
    """
    Invariant 6: Substring quote validation must reject hallucinated quotes.
    """
    project = test_setup["project"]
    meeting = test_setup["meeting"]

    item_halluc = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Use Provider C for India settlements",
        evidence_quote="Provider C for India",
        review_state=ReviewState.approved,
    )
    db_session.add(item_halluc)
    db_session.flush()

    d_halluc = Decision(
        item_id=item_halluc.id,
        text="Use Provider C for India settlements",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d_halluc)
    db_session.commit()

    # Enqueue fake response with fake quote that does not appear anywhere
    adapter.enqueue_fake_response({
        "verdict": "supersedes",
        "confidence": 0.95,
        "explanation": "Switching providers",
        "old_quote": "NON_EXISTENT_FABRICATED_QUOTE_12345",
        "new_quote": "Provider C for India",
    })

    alerts = detect_conflicts_for_decision(db_session, d_halluc)
    # Hallucination dropped
    assert len(alerts) == 0


def test_ambiguous_conflict_creates_card_for_reviewer(db_session: Session, test_setup):
    """
    Ambiguous confidence (0.4 to 0.7) creates a card asking reviewer to decide.
    """
    project = test_setup["project"]
    meeting = test_setup["meeting"]

    item_ambig = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Review alternative routing for India settlements",
        evidence_quote="alternative routing for India",
        review_state=ReviewState.approved,
    )
    db_session.add(item_ambig)
    db_session.flush()

    d_ambig = Decision(
        item_id=item_ambig.id,
        text="Review alternative routing for India settlements",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d_ambig)
    db_session.commit()

    adapter.enqueue_fake_response({
        "verdict": "contradicts",
        "confidence": 0.55,
        "explanation": "Might partially overlap with Provider A exclusivity.",
        "old_quote": "India settlements",
        "new_quote": "India settlements",
    })

    alerts = detect_conflicts_for_decision(db_session, d_ambig)
    assert len(alerts) == 1
    assert alerts[0].verdict == "ambiguous_contradicts"
    assert "Reviewer confirmation needed" in alerts[0].explanation


def test_duplicate_decision_creates_possible_duplicate_alert(db_session: Session, test_setup):
    """
    Duplicates creates a low-priority 'possible duplicate' card.
    """
    project = test_setup["project"]
    meeting = test_setup["meeting"]

    item_dup = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Adopt Provider A for India settlements",
        evidence_quote="Provider A for India settlements",
        review_state=ReviewState.approved,
    )
    db_session.add(item_dup)
    db_session.flush()

    d_dup = Decision(
        item_id=item_dup.id,
        text="Adopt Provider A for India settlements",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d_dup)
    db_session.commit()

    adapter.enqueue_fake_response({
        "verdict": "duplicates",
        "confidence": 0.90,
        "explanation": "Identical meaning to the earlier Provider A decision.",
        "old_quote": "Provider A for India settlements",
        "new_quote": "Provider A for India settlements",
    })
    # For any secondary candidates, return unrelated
    adapter.enqueue_fake_response({
        "verdict": "unrelated",
        "confidence": 0.95,
        "explanation": "Different topic.",
        "old_quote": "Dec 15",
        "new_quote": "Provider A",
    })

    alerts = detect_conflicts_for_decision(db_session, d_dup)
    assert len(alerts) == 1
    assert alerts[0].verdict == "possible_duplicate"
    assert "[Low Priority]" in alerts[0].explanation
