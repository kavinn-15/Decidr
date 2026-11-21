import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db, SessionLocal, engine, init_db
from app.models.models import (
    Person,
    Meeting,
    Item,
    Decision,
    Premise,
    Task,
    Link,
    Alert,
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
)
from app.services.blast_radius import calculate_blast_radius


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


@pytest.fixture
def gold_approvals_fixture(db_session: Session):
    """
    Applies the gold approved decisions, premises, tasks, and links:
    - P1 supports D1
    - T1 (20h) and T2 (None) implement D1 (confirmed)
    - D3 depends_on D1 (confirmed)
    - T6 (15h) implements D3 (confirmed)
    - T5 (10h, Europe) has no link to D1/D3
    - SLA task (5h) has an UNCONFIRMED link to D1
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Payments Revamp {uid}"

    # People
    p_ravi = Person(name=f"Ravi {uid}", email=f"ravi_{uid}@test.local", tracker_id=f"TRK-R-{uid}")
    p_meera = Person(name=f"Meera {uid}", email=f"meera_{uid}@test.local", tracker_id=f"TRK-M-{uid}")
    p_divya = Person(name=f"Divya {uid}", email=f"divya_{uid}@test.local", tracker_id=f"TRK-D-{uid}")
    db_session.add_all([p_ravi, p_meera, p_divya])
    db_session.flush()

    # M1 India Meeting
    m1 = Meeting(
        title=f"M1 Kickoff {uid}",
        date=date(2026, 11, 2),
        project=project,
        region="India",
        transcript_ref="seed/m1.vtt",
        status=MeetingStatus.done,
    )
    # Europe Meeting for T5
    m_eu = Meeting(
        title=f"M Europe {uid}",
        date=date(2026, 11, 5),
        project=project,
        region="Europe",
        transcript_ref="seed/m_eu.vtt",
        status=MeetingStatus.done,
    )
    db_session.add_all([m1, m_eu])
    db_session.flush()

    # D1 (India)
    item_d1 = Item(
        meeting_id=m1.id,
        type=ItemType.decision,
        text="Use Provider A for India settlements",
        evidence_quote="we will use Provider A for India settlements.",
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

    # P1 (supports D1)
    p1 = Premise(
        decision_id=d1.id,
        text="Provider A supports T+0 UPI settlement",
        evidence_quote="Provider A supports T+0 UPI settlement",
        scope_project=project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p1)
    db_session.flush()

    # D3 (Transitive decision: depends on D1)
    item_d3 = Item(
        meeting_id=m1.id,
        type=ItemType.decision,
        text="Deploy automated settlement webhook",
        evidence_quote="automated settlement webhook",
        review_state=ReviewState.approved,
    )
    db_session.add(item_d3)
    db_session.flush()

    d3 = Decision(
        item_id=item_d3.id,
        text="Deploy automated settlement webhook",
        scope_project=project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d3)
    db_session.flush()

    # Link: D3 depends_on D1 (confirmed)
    link_d3_d1 = Link(
        source_type="decision",
        source_id=d3.id,
        target_type="decision",
        target_id=d1.id,
        relation=LinkRelation.depends_on,
        confirmed=True,
    )
    db_session.add(link_d3_d1)

    # T1: Integrate Provider A SDK (20h, confirmed implements D1)
    item_t1 = Item(
        meeting_id=m1.id,
        type=ItemType.action,
        text="Integrate Provider A SDK",
        evidence_quote="integrate Provider A SDK by Nov 20",
        review_state=ReviewState.approved,
    )
    db_session.add(item_t1)
    db_session.flush()

    t1 = Task(
        item_id=item_t1.id,
        decision_id=d1.id,
        title="Integrate Provider A SDK",
        owner_id=p_ravi.id,
        due_date=date(2026, 11, 20),
        estimate_hours=20.0,
        status=TaskStatus.open,
    )
    db_session.add(t1)
    db_session.flush()

    link_t1 = Link(
        source_type="task",
        source_id=t1.id,
        target_type="decision",
        target_id=d1.id,
        relation=LinkRelation.implements,
        confirmed=True,
    )
    db_session.add(link_t1)

    # T2: Build settlement reconciliation screen (None estimate, confirmed implements D1)
    item_t2 = Item(
        meeting_id=m1.id,
        type=ItemType.action,
        text="Build settlement reconciliation screen",
        evidence_quote="build settlement reconciliation screen",
        review_state=ReviewState.approved,
    )
    db_session.add(item_t2)
    db_session.flush()

    t2 = Task(
        item_id=item_t2.id,
        decision_id=d1.id,
        title="Build settlement reconciliation screen",
        owner_id=p_meera.id,
        estimate_hours=None,  # Unestimated!
        status=TaskStatus.open,
    )
    db_session.add(t2)
    db_session.flush()

    link_t2 = Link(
        source_type="task",
        source_id=t2.id,
        target_type="decision",
        target_id=d1.id,
        relation=LinkRelation.implements,
        confirmed=True,
    )
    db_session.add(link_t2)

    # T6: Configure webhook retry queue (15h, confirmed implements D3)
    item_t6 = Item(
        meeting_id=m1.id,
        type=ItemType.action,
        text="Configure webhook retry queue",
        evidence_quote="configure webhook retry queue",
        review_state=ReviewState.approved,
    )
    db_session.add(item_t6)
    db_session.flush()

    t6 = Task(
        item_id=item_t6.id,
        decision_id=d3.id,
        title="Configure webhook retry queue",
        owner_id=p_ravi.id,
        estimate_hours=15.0,
        status=TaskStatus.open,
    )
    db_session.add(t6)
    db_session.flush()

    link_t6 = Link(
        source_type="task",
        source_id=t6.id,
        target_type="decision",
        target_id=d3.id,
        relation=LinkRelation.implements,
        confirmed=True,
    )
    db_session.add(link_t6)

    # T5: Evaluate Provider B for Europe (10h, Europe meeting)
    item_t5 = Item(
        meeting_id=m_eu.id,
        type=ItemType.action,
        text="Evaluate Provider B for Europe",
        evidence_quote="evaluate Provider B for Europe",
        review_state=ReviewState.approved,
    )
    db_session.add(item_t5)
    db_session.flush()

    t5 = Task(
        item_id=item_t5.id,
        decision_id=None,
        title="Evaluate Provider B for Europe",
        owner_id=p_divya.id,
        estimate_hours=10.0,
        status=TaskStatus.open,
    )
    db_session.add(t5)

    # T_SLA: Review the vendor SLA (5h, UNCONFIRMED link to D1)
    item_sla = Item(
        meeting_id=m1.id,
        type=ItemType.action,
        text="Review the vendor SLA",
        evidence_quote="someone should review the vendor SLA",
        review_state=ReviewState.approved,
    )
    db_session.add(item_sla)
    db_session.flush()

    t_sla = Task(
        item_id=item_sla.id,
        decision_id=None,
        title="Review the vendor SLA",
        estimate_hours=5.0,
        status=TaskStatus.open,
    )
    db_session.add(t_sla)
    db_session.flush()

    # Unconfirmed link!
    link_sla = Link(
        source_type="task",
        source_id=t_sla.id,
        target_type="decision",
        target_id=d1.id,
        relation=LinkRelation.implements,
        confirmed=False,  # Unconfirmed!
    )
    db_session.add(link_sla)

    # Alert on P1 (M2 trigger: Sam says Provider A supports only T+2)
    alert = Alert(
        kind=AlertKind.premise_break,
        meeting_id=m1.id,
        premise_id=p1.id,
        decision_id=d1.id,
        verdict="premise_break",
        old_quote="Provider A supports T+0 UPI settlement",
        new_quote="Provider A supports only T+2",
        explanation="Speaker: Sam. Sam (M2, Nov 9) says Provider A supports only T+2",
        state=AlertState.open,
    )
    db_session.add(alert)
    db_session.commit()

    return {
        "project": project,
        "p1": p1,
        "d1": d1,
        "d3": d3,
        "t1": t1,
        "t2": t2,
        "t6": t6,
        "t5": t5,
        "t_sla": t_sla,
        "alert": alert,
    }


def test_blast_radius_breaking_p1_affects_t1_t2_and_t6_via_d3(db_session: Session, gold_approvals_fixture):
    """
    Test: breaking P1 affects T1 and T2 at depth 1 and T6 at depth 2 via D3.
    Unconfirmed links are never traversed.
    """
    p1 = gold_approvals_fixture["p1"]
    t1 = gold_approvals_fixture["t1"]
    t2 = gold_approvals_fixture["t2"]
    t6 = gold_approvals_fixture["t6"]
    t_sla = gold_approvals_fixture["t_sla"]
    alert = gold_approvals_fixture["alert"]

    res = calculate_blast_radius(db_session, premise_id=p1.id, alert=alert)

    affected = res["affected"]
    affected_ids = {item["id"] for item in affected}

    # Must contain T1, T2, and T6
    assert t1.id in affected_ids
    assert t2.id in affected_ids
    assert t6.id in affected_ids

    # Invariant 4: SLA task has unconfirmed link -> MUST NOT be in affected!
    assert t_sla.id not in affected_ids

    # Verify depths
    t1_item = next(item for item in affected if item["id"] == t1.id)
    t2_item = next(item for item in affected if item["id"] == t2.id)
    t6_item = next(item for item in affected if item["id"] == t6.id)

    assert t1_item["depth"] == 1
    assert t2_item["depth"] == 1
    assert t6_item["depth"] == 2  # Depth 2 via D3!

    # Verify exact chain for T6
    t6_node_labels = [n["label"] for n in t6_item["chain_nodes"]]
    assert t6_node_labels == [f"P{p1.id}", f"D{gold_approvals_fixture['d1'].id}", f"D{gold_approvals_fixture['d3'].id}", f"T{t6.id}"]

    # Verify templated reason string
    assert "undermines premise" in t1_item["reason"]
    assert "justifies T" in t1_item["reason"]
    assert "depends on" in t6_item["reason"]


def test_t5_europe_listed_unaffected_with_scope_reason(db_session: Session, gold_approvals_fixture):
    """
    Test: T5 (Europe) is listed unaffected with the scope reason ("scope differs: Europe vs India").
    """
    p1 = gold_approvals_fixture["p1"]
    t5 = gold_approvals_fixture["t5"]
    alert = gold_approvals_fixture["alert"]

    res = calculate_blast_radius(db_session, premise_id=p1.id, alert=alert)

    unaffected = res["unaffected"]
    unaffected_ids = {item["id"] for item in unaffected}

    assert t5.id in unaffected_ids

    t5_item = next(item for item in unaffected if item["id"] == t5.id)
    assert "scope differs: Europe vs India" in t5_item["reason"]


def test_sla_task_listed_as_needs_confirmation(db_session: Session, gold_approvals_fixture):
    """
    Test: The SLA task with an unconfirmed link is listed as needs confirmation ("needs confirmation, nothing changed").
    """
    p1 = gold_approvals_fixture["p1"]
    t_sla = gold_approvals_fixture["t_sla"]
    alert = gold_approvals_fixture["alert"]

    res = calculate_blast_radius(db_session, premise_id=p1.id, alert=alert)

    needs_conf = res["needs_confirmation"]
    needs_conf_ids = {item["id"] for item in needs_conf}

    assert t_sla.id in needs_conf_ids

    sla_item = next(item for item in needs_conf if item["id"] == t_sla.id)
    assert sla_item["reason"] == "needs confirmation, nothing changed"


def test_hours_at_risk_metrics_never_guesses_estimates(db_session: Session, gold_approvals_fixture):
    """
    Invariant 10: hours_at_risk = sum of estimate_hours of affected open tasks,
    plus a count of unestimated tasks (never guess an estimate).
    T1 = 20h, T6 = 15h, T2 = None (unestimated).
    Sum = 35.0, unestimated = 1.
    """
    p1 = gold_approvals_fixture["p1"]
    alert = gold_approvals_fixture["alert"]

    res = calculate_blast_radius(db_session, premise_id=p1.id, alert=alert)
    metrics = res["metrics"]

    assert metrics["hours_at_risk"] == 35.0
    assert metrics["unestimated_count"] == 1
    assert metrics["total_affected"] == 3
    assert metrics["direct_affected"] == 2
    assert metrics["indirect_affected"] == 1


def test_api_get_alert_blast_radius(client: TestClient, gold_approvals_fixture):
    """
    Verify GET /alerts/{id}/blast-radius endpoint.
    """
    alert = gold_approvals_fixture["alert"]

    res = client.get(f"/alerts/{alert.id}/blast-radius")
    assert res.status_code == 200
    data = res.json()

    assert data["alert_id"] == alert.id
    assert "trigger_evidence" in data
    assert "metrics" in data
    assert data["metrics"]["hours_at_risk"] == 35.0
    assert len(data["affected"]) == 3
    assert len(data["unaffected"]) >= 1
    assert len(data["needs_confirmation"]) >= 1


def test_api_get_alert_blast_radius_not_found(client: TestClient):
    res = client.get("/alerts/999999/blast-radius")
    assert res.status_code == 404
