import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.db.session import get_db, SessionLocal, engine, Base, init_db
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
from app.services.premise_watch import watch_meeting_utterances, run_expiry


@pytest.fixture
def db_session():
    init_db(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def configure_fake_llm():
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
def watch_setup(db_session: Session):
    uid = uuid.uuid4().hex[:6]
    project = f"Payments Revamp {uid}"

    person = Person(
        name=f"Sam {uid}",
        email=f"sam_{uid}@example.com",
        tracker_id=f"SAM-{uid}",
    )
    db_session.add(person)
    db_session.flush()

    # M1 Meeting
    m1 = Meeting(
        title=f"M1 Kickoff {uid}",
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
        text="Use Provider A for India settlements",
        evidence_quote="Provider A for India settlements",
        review_state=ReviewState.approved,
    )
    db_session.add(item_d1)
    db_session.flush()

    d1 = Decision(
        item_id=item_d1.id,
        text="Use Provider A for India settlements",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d1)
    db_session.flush()

    # P1: Confirmed premise for D1
    p1 = Premise(
        decision_id=d1.id,
        text="Provider A supports T+0 UPI settlement in India",
        evidence_quote="Provider A supports T+0 UPI settlement",
        scope_project=project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p1)

    # P2: Budget confirmed premise
    p2 = Premise(
        decision_id=d1.id,
        text="Budget of 8 lakh is approved through Q1",
        evidence_quote="Budget of 8 lakh is approved through Q1",
        scope_project=project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p2)

    # P3: Ravi availability
    p3 = Premise(
        decision_id=d1.id,
        text="Ravi is available full time until Dec 5",
        evidence_quote="Ravi is available full time until Dec 5",
        scope_project=project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p3)

    db_session.commit()

    return {
        "project": project,
        "m1": m1,
        "d1": d1,
        "p1": p1,
        "p2": p2,
        "p3": p3,
        "person": person,
    }


def test_m2_sams_t2_remark_creates_break_alert_on_p1_without_mentioning_d1(
    db_session: Session,
    watch_setup,
):
    """
    Test: M2 Sam's T+2 remark creates a break alert on P1 without any mention of D1.
    Human confirmation breaks P1; dismissing restores it to holding.
    """
    project = watch_setup["project"]
    p1 = watch_setup["p1"]
    person = watch_setup["person"]

    # M2 Meeting
    m2 = Meeting(
        title="M2 Sync",
        date=date(2026, 11, 9),
        project=project,
        region="India",
        transcript_ref="seed/m2.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(m2)
    db_session.flush()

    u1 = Utterance(
        meeting_id=m2.id,
        idx=0,
        speaker_raw="Asha",
        text="Let's quickly check in on vendor integrations.",
    )
    u2 = Utterance(
        meeting_id=m2.id,
        idx=1,
        speaker_raw="Sam",
        person_id=person.id,
        text="By the way, Provider A told me they only support T+2 settlement, not T+0.",
    )
    u3 = Utterance(
        meeting_id=m2.id,
        idx=2,
        speaker_raw="Meera",
        text="That will require changes to reconciliation screens.",
    )
    db_session.add_all([u1, u2, u3])
    db_session.commit()

    # Enqueue fake judge response
    adapter.enqueue_fake_response({
        "evaluations": [
            {
                "premise_id": p1.id,
                "verdict": "undermines",
                "confidence": 0.95,
                "explanation": "Provider A told Sam they only support T+2 settlement, directly contradicting T+0.",
                "new_quote": "only support T+2 settlement, not T+0",
            }
        ]
    })

    alerts = watch_meeting_utterances(db_session, m2.id)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.kind == AlertKind.premise_break
    assert alert.premise_id == p1.id
    assert alert.verdict == "premise_break"
    assert alert.old_quote == p1.evidence_quote
    assert alert.new_quote == "only support T+2 settlement, not T+0"
    assert alert.state == AlertState.open

    # Invariant: Premise becomes broken ONLY when a human confirms the alert!
    db_session.refresh(p1)
    assert p1.status == PremiseStatus.holding


def test_m2_karthik_budget_still_holds_creates_no_alert(
    db_session: Session,
    watch_setup,
):
    """
    Test: M2 Karthik's "budget still holds" creates no alert and updates last_supported_at.
    """
    project = watch_setup["project"]
    p2 = watch_setup["p2"]

    m2 = Meeting(
        title="M2 Finance Sync",
        date=date(2026, 11, 9),
        project=project,
        region="India",
        transcript_ref="seed/m2.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(m2)
    db_session.flush()

    u = Utterance(
        meeting_id=m2.id,
        idx=0,
        speaker_raw="Karthik",
        text="Just confirming that the budget of 8 lakh still holds through Q1.",
    )
    db_session.add(u)
    db_session.commit()

    adapter.enqueue_fake_response({
        "evaluations": [
            {
                "premise_id": p2.id,
                "verdict": "supports",
                "confidence": 0.95,
                "explanation": "Karthik confirmed that the 8 lakh budget still holds.",
                "new_quote": "budget of 8 lakh still holds through Q1",
            }
        ]
    })

    alerts = watch_meeting_utterances(db_session, m2.id)
    assert len(alerts) == 0

    db_session.refresh(p2)
    assert p2.last_supported_at is not None


def test_europe_statement_does_not_undermine_india_premise(
    db_session: Session,
    watch_setup,
):
    """
    Test: The Europe statement does not undermine the India premise (disjoint scopes).
    """
    project = watch_setup["project"]

    # Europe meeting: region is Europe
    m_europe = Meeting(
        title="Europe Expansion",
        date=date(2026, 11, 9),
        project=project,
        region="Europe",
        transcript_ref="seed/m_eur.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(m_europe)
    db_session.flush()

    u = Utterance(
        meeting_id=m_europe.id,
        idx=0,
        speaker_raw="Divya",
        text="Provider B in Europe only supports T+2 settlement for SEPA.",
    )
    db_session.add(u)
    db_session.commit()

    # Europe region is disjoint with India premises P1, P2, P3 -> 0 alerts created
    alerts = watch_meeting_utterances(db_session, m_europe.id)
    assert len(alerts) == 0


def test_m3_ravi_leave_creates_break_alert_on_p3(
    db_session: Session,
    watch_setup,
):
    """
    Test: M3 Ravi's leave creates a break alert on P3.
    """
    project = watch_setup["project"]
    p3 = watch_setup["p3"]

    m3 = Meeting(
        title="M3 Standup",
        date=date(2026, 11, 16),
        project=project,
        region="India",
        transcript_ref="seed/m3.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(m3)
    db_session.flush()

    u = Utterance(
        meeting_id=m3.id,
        idx=0,
        speaker_raw="Ravi",
        text="I need to take unexpected medical leave starting Nov 25.",
    )
    db_session.add(u)
    db_session.commit()

    adapter.enqueue_fake_response({
        "evaluations": [
            {
                "premise_id": p3.id,
                "verdict": "undermines",
                "confidence": 0.92,
                "explanation": "Ravi's leave starting Nov 25 breaks his full-time availability until Dec 5.",
                "new_quote": "medical leave starting Nov 25",
            }
        ]
    })

    alerts = watch_meeting_utterances(db_session, m3.id)
    assert len(alerts) == 1
    assert alerts[0].kind == AlertKind.premise_break
    assert alerts[0].premise_id == p3.id
    assert alerts[0].new_quote == "medical leave starting Nov 25"


def test_m4_sandbox_premise_expires_with_as_of_dec_1_and_not_nov_25(
    db_session: Session,
    watch_setup,
):
    """
    Test: M4 sandbox premise expires with as_of 2026-12-01 and not with 2026-11-25.
    Premises within 7 days of valid_until become shaky.
    """
    project = watch_setup["project"]
    d1 = watch_setup["d1"]

    # Sandbox premise valid until Nov 30, 2026
    p_sandbox = Premise(
        decision_id=d1.id,
        text="Testing sandbox access is valid until Nov 30",
        evidence_quote="sandbox access is valid until Nov 30",
        scope_project=project,
        valid_until=date(2026, 11, 30),
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p_sandbox)
    db_session.commit()

    # 1. As of 2026-11-25: within 7 days of Nov 30 -> becomes shaky, does NOT expire
    alerts_nov25 = run_expiry(db_session, as_of=date(2026, 11, 25))
    assert len(alerts_nov25) == 0

    db_session.refresh(p_sandbox)
    assert p_sandbox.status == PremiseStatus.shaky

    # 2. As of 2026-12-01: past Nov 30 -> marks expired, creates expiry alert
    alerts_dec01 = run_expiry(db_session, as_of=date(2026, 12, 1))
    assert len(alerts_dec01) == 1
    assert alerts_dec01[0].kind == AlertKind.expiry
    assert alerts_dec01[0].premise_id == p_sandbox.id

    db_session.refresh(p_sandbox)
    assert p_sandbox.status == PremiseStatus.expired


def test_unconfirmed_premise_is_never_checked(
    db_session: Session,
    watch_setup,
):
    """
    Invariant 4: An unconfirmed premise (state=proposed) is never checked.
    """
    project = watch_setup["project"]
    d1 = watch_setup["d1"]

    # Unconfirmed premise
    p_unconfirmed = Premise(
        decision_id=d1.id,
        text="Unverified assumption about settlement fees",
        evidence_quote="settlement fees assumption",
        scope_project=project,
        scope_region="India",
        state=PremiseState.proposed,  # Unconfirmed!
        status=PremiseStatus.holding,
    )
    db_session.add(p_unconfirmed)

    m = Meeting(
        title="Fees Review",
        date=date(2026, 11, 9),
        project=project,
        region="India",
        transcript_ref="seed/m.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(m)
    db_session.flush()

    u = Utterance(
        meeting_id=m.id,
        idx=0,
        speaker_raw="Asha",
        text="The settlement fees assumption is completely false and wrong.",
    )
    db_session.add(u)
    db_session.commit()

    # Even though utterance matches, unconfirmed premise is excluded
    alerts = watch_meeting_utterances(db_session, m.id)
    assert len(alerts) == 0


def test_api_admin_run_expiry(client: TestClient, db_session: Session, watch_setup):
    """
    Verify POST /admin/run-expiry?as_of=YYYY-MM-DD endpoint.
    """
    res = client.post("/admin/run-expiry?as_of=2026-12-05")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["as_of"] == "2026-12-05"
    assert "alerts_created" in data
