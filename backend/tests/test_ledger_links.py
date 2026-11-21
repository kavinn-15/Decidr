import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db, SessionLocal, engine, Base, init_db
from app.models.models import (
    Person,
    Meeting,
    Item,
    Decision,
    DecisionVersion,
    Premise,
    Task,
    Link,
    AuditLog,
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
)
from app.services.ledger import scope_overlap, search as search_decisions
from app.services.links import (
    create_link,
    confirm_link,
    reject_link,
    neighbors,
)


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


# ==========================================
# 1. Pure Scope Overlap Tests
# ==========================================

def test_scope_overlap_india_vs_europe_is_disjoint():
    """Rule 2: Non-null regions that differ must be disjoint."""
    scope_a = {"project": "Payments Revamp", "region": "India"}
    scope_b = {"project": "Payments Revamp", "region": "Europe"}
    assert scope_overlap(scope_a, scope_b) == "disjoint"


def test_scope_overlap_same_scope_overlaps():
    """Rule 5: Identical scopes must overlap."""
    scope_a = {"project": "Payments Revamp", "region": "India", "release": "v1.0"}
    scope_b = {"project": "Payments Revamp", "region": "India", "release": "v1.0"}
    assert scope_overlap(scope_a, scope_b) == "overlap"

    # Also without region/release
    global_a = {"project": "Payments Revamp"}
    global_b = {"project": "Payments Revamp"}
    assert scope_overlap(global_a, global_b) == "overlap"


def test_scope_overlap_non_intersecting_dates_are_disjoint():
    """Rule 4: Non-intersecting effective dates must be disjoint."""
    scope_a = {
        "project": "Payments Revamp",
        "effective_from": date(2026, 11, 1),
        "effective_to": date(2026, 11, 10),
    }
    scope_b = {
        "project": "Payments Revamp",
        "effective_from": date(2026, 11, 15),
        "effective_to": date(2026, 11, 25),
    }
    assert scope_overlap(scope_a, scope_b) == "disjoint"
    # Reverse symmetry
    assert scope_overlap(scope_b, scope_a) == "disjoint"


def test_scope_overlap_one_side_null_and_unknown():
    """
    Rule 6: One side null encompasses specific scope (overlap).
    Rule 7: Cross-unspecified dimensions return unknown.
    Rule 1: Different projects are disjoint; missing projects are unknown.
    """
    # Global encompasses regional
    regional = {"project": "Payments Revamp", "region": "India"}
    global_scope = {"project": "Payments Revamp", "region": None}
    assert scope_overlap(regional, global_scope) == "overlap"
    assert scope_overlap(global_scope, regional) == "overlap"

    # Cross-unspecified: A has region, B has release
    cross_a = {"project": "Payments Revamp", "region": "India", "release": None}
    cross_b = {"project": "Payments Revamp", "region": None, "release": "v2.0"}
    assert scope_overlap(cross_a, cross_b) == "unknown"

    # Different projects
    diff_proj_a = {"project": "Alpha", "region": "India"}
    diff_proj_b = {"project": "Beta", "region": "India"}
    assert scope_overlap(diff_proj_a, diff_proj_b) == "disjoint"

    # Missing project
    no_proj_a = {"project": None, "region": "India"}
    assert scope_overlap(no_proj_a, regional) == "unknown"


# ==========================================
# 2. Links Service Tests
# ==========================================

def test_unconfirmed_links_excluded_from_neighbors(db_session: Session):
    """
    Invariant 4: Graph queries must ignore unconfirmed links by default (confirmed_only=True).
    """
    task_id = 991
    decision_id = 881

    # Create unconfirmed link
    link = create_link(
        db=db_session,
        source_type="task",
        source_id=task_id,
        target_type="decision",
        target_id=decision_id,
        relation=LinkRelation.implements,
        confirmed=False,
        confidence=0.85,
        rationale="Integrates Provider A for India",
        actor="test_user",
    )
    db_session.commit()

    # Confirmed only by default -> must exclude unconfirmed links
    task_neighbors = neighbors(db_session, ("task", task_id))
    assert len(task_neighbors) == 0

    dec_neighbors = neighbors(db_session, ("decision", decision_id))
    assert len(dec_neighbors) == 0

    # Including unconfirmed links explicitly
    all_neighbors = neighbors(db_session, ("task", task_id), confirmed_only=False)
    assert len(all_neighbors) == 1
    assert all_neighbors[0]["node_type"] == "decision"
    assert all_neighbors[0]["node_id"] == decision_id
    assert all_neighbors[0]["confirmed"] is False


def test_links_service_create_confirm_reject(db_session: Session):
    """
    Verify create_link, confirm_link, reject_link state and audit logging.
    """
    task_id = 992
    decision_id = 882

    # 1. Create link
    link = create_link(
        db=db_session,
        source_type="task",
        source_id=task_id,
        target_type="decision",
        target_id=decision_id,
        relation=LinkRelation.implements,
        confirmed=False,
        actor="reviewer_alice",
    )
    db_session.commit()
    assert link.id is not None
    assert link.confirmed is False

    # Check audit log for create_link
    audit_create = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == "link", AuditLog.entity_id == link.id, AuditLog.action == "create_link")
        .first()
    )
    assert audit_create is not None
    assert audit_create.actor == "reviewer_alice"

    # 2. Confirm link
    confirmed_link = confirm_link(db_session, link.id, actor="reviewer_bob")
    db_session.commit()
    assert confirmed_link.confirmed is True

    # Check neighbors now returns it
    confirmed_neighbors = neighbors(db_session, ("task", task_id))
    assert len(confirmed_neighbors) == 1
    assert confirmed_neighbors[0]["node_type"] == "decision"
    assert confirmed_neighbors[0]["node_id"] == decision_id
    assert confirmed_neighbors[0]["confirmed"] is True

    # 3. Reject link
    rejected_link = reject_link(db_session, link.id, actor="reviewer_carol")
    db_session.commit()
    assert rejected_link.confirmed is False

    # Neighbors now excludes it again
    assert len(neighbors(db_session, ("task", task_id))) == 0


# ==========================================
# 3. Ledger Search & BM25 Ranking Tests
# ==========================================

@pytest.fixture
def seeded_decisions(db_session: Session):
    uid = uuid.uuid4().hex[:6]
    person = Person(
        name=f"Lead {uid}",
        email=f"lead_{uid}@example.com",
        tracker_id=f"TRK-{uid}",
    )
    db_session.add(person)
    db_session.flush()

    meeting = Meeting(
        title=f"Payments Review {uid}",
        date=date(2026, 11, 2),
        project=f"Payments Revamp {uid}",
        region="India",
        transcript_ref="seed/m1.vtt",
        status=MeetingStatus.done,
    )
    db_session.add(meeting)
    db_session.flush()

    # D1: Provider A India
    item1 = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Use Provider A for India settlements",
        evidence_quote="Provider A for India",
        review_state=ReviewState.approved,
    )
    db_session.add(item1)
    db_session.flush()

    d1 = Decision(
        item_id=item1.id,
        text="Use Provider A for India settlements",
        scope_project=meeting.project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d1)
    db_session.flush()

    p1 = Premise(
        decision_id=d1.id,
        text="Provider A supports T+0 UPI settlement in India",
        evidence_quote="T+0 UPI settlement",
        scope_project=meeting.project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p1)

    # D2: Launch Date India
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
        scope_project=meeting.project,
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d2)
    db_session.flush()

    p2 = Premise(
        decision_id=d2.id,
        text="Ravi is available full time until Dec 5",
        evidence_quote="Ravi is available full time",
        scope_project=meeting.project,
        scope_region="India",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p2)

    # D3: Provider B Europe
    item3 = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Evaluate Provider B for Europe payments",
        evidence_quote="Provider B for Europe",
        review_state=ReviewState.approved,
    )
    db_session.add(item3)
    db_session.flush()

    d3 = Decision(
        item_id=item3.id,
        text="Evaluate Provider B for Europe payments",
        scope_project=meeting.project,
        scope_region="Europe",
        status=DecisionStatus.active,
        version=1,
    )
    db_session.add(d3)
    db_session.flush()

    p3 = Premise(
        decision_id=d3.id,
        text="European banking compliance mandates SEPA certification",
        evidence_quote="compliance mandates SEPA",
        scope_project=meeting.project,
        scope_region="Europe",
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db_session.add(p3)

    db_session.commit()
    return {
        "project": meeting.project,
        "d1": d1,
        "d2": d2,
        "d3": d3,
        "person": person,
    }


def test_search_ranks_exact_topic_decision_first(db_session: Session, seeded_decisions):
    """
    BM25 over decision text plus premise text must rank the exact-topic decision first.
    """
    project = seeded_decisions["project"]
    d1 = seeded_decisions["d1"]

    # Query matching D1 text and premise
    results = search_decisions(
        db=db_session,
        project=project,
        text="Provider A T+0 UPI settlement",
    )

    assert len(results) >= 1
    top_hit = results[0]
    assert top_hit["decision"].id == d1.id
    assert top_hit["score"] > 0
    # D1 score should be strictly higher than other decisions
    if len(results) > 1:
        assert top_hit["score"] > results[1]["score"]


def test_search_scope_and_status_filtering(db_session: Session, seeded_decisions):
    """
    Scope filter applied first: India query with scope region=India excludes Europe.
    """
    project = seeded_decisions["project"]

    # Scope filter for region "India"
    results = search_decisions(
        db=db_session,
        project=project,
        scope={"project": project, "region": "India"},
    )
    assert len(results) == 2
    regions = {r["decision"].scope_region for r in results}
    assert "Europe" not in regions
    assert "India" in regions


# ==========================================
# 4. REST API Endpoint Tests
# ==========================================

def test_api_get_decisions(client: TestClient, seeded_decisions):
    project = seeded_decisions["project"]
    d1 = seeded_decisions["d1"]

    # GET /decisions?project=...
    res = client.get(f"/decisions?project={project}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3

    # Search with text ranking
    res_search = client.get(f"/decisions?project={project}&text=Provider+A+settlement")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert len(search_data) >= 1
    assert search_data[0]["id"] == d1.id


def test_api_get_decision_detail(client: TestClient, db_session: Session, seeded_decisions):
    d1 = seeded_decisions["d1"]
    person = seeded_decisions["person"]

    # Create linked task directly
    item_task = Item(
        meeting_id=d1.item.meeting_id,
        type=ItemType.action,
        text="Integrate Provider A SDK",
        evidence_quote="Provider A SDK",
        review_state=ReviewState.approved,
    )
    db_session.add(item_task)
    db_session.flush()

    task = Task(
        item_id=item_task.id,
        decision_id=d1.id,
        title="Integrate Provider A SDK",
        owner_id=person.id,
        due_date=date(2026, 11, 20),
        status=TaskStatus.open,
    )
    db_session.add(task)

    # Create version history
    v1 = DecisionVersion(
        decision_id=d1.id,
        version=1,
        text=d1.text,
        changed_by="PM Asha",
    )
    db_session.add(v1)

    # Create audit log entry for status timeline
    audit_entry = AuditLog(
        actor="PM Asha",
        action="approve_decision",
        entity_type="decision",
        entity_id=d1.id,
        before=None,
        after={"status": "active"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(audit_entry)
    db_session.commit()

    # Call GET /decisions/{id}
    res = client.get(f"/decisions/{d1.id}")
    assert res.status_code == 200
    detail = res.json()

    # Verify all 5 components of decision detail
    assert "decision" in detail
    assert detail["decision"]["id"] == d1.id
    assert detail["decision"]["scope_region"] == "India"

    assert "premises" in detail
    assert len(detail["premises"]) >= 1
    assert detail["premises"][0]["status"] == "holding"

    assert "linked_tasks" in detail
    assert len(detail["linked_tasks"]) == 1
    assert detail["linked_tasks"][0]["title"] == "Integrate Provider A SDK"

    assert "version_history" in detail
    assert len(detail["version_history"]) == 1
    assert detail["version_history"][0]["version"] == 1

    assert "status_timeline" in detail
    assert len(detail["status_timeline"]) >= 1
    assert detail["status_timeline"][0]["action"] == "approve_decision"


def test_api_get_decision_not_found(client: TestClient):
    res = client.get("/decisions/999999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Decision not found"
