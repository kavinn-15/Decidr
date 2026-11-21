import uuid
from datetime import date
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db, engine
from app.models.models import (
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
)
from app.services.blast_radius import calculate_blast_radius


@pytest.fixture
def db():
    init_db(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_circular_dependencies_handled_gracefully_without_infinite_loop(db: Session):
    """
    Phase 6: Circular dependencies in decisions (D1 depends on D2, D2 depends on D1)
    must terminate safely via BFS visited_decisions set without stack overflow or infinite loop.
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Circular Graph {uid}"

    m = Meeting(
        title="Circular Arch Meeting",
        date=date(2026, 11, 2),
        project=project,
        region="India",
        transcript_ref="seed/m.vtt",
        status=MeetingStatus.done,
    )
    db.add(m)
    db.flush()

    item_d1 = Item(meeting_id=m.id, type=ItemType.decision, text="Decision 1", evidence_quote="D1", review_state=ReviewState.approved)
    item_d2 = Item(meeting_id=m.id, type=ItemType.decision, text="Decision 2", evidence_quote="D2", review_state=ReviewState.approved)
    db.add_all([item_d1, item_d2])
    db.flush()

    d1 = Decision(item_id=item_d1.id, text="Decision 1", scope_project=project, status=DecisionStatus.active, version=1)
    d2 = Decision(item_id=item_d2.id, text="Decision 2", scope_project=project, status=DecisionStatus.active, version=1)
    db.add_all([d1, d2])
    db.flush()

    # Circular depends_on links: D2 depends on D1, D1 depends on D2
    link_d2_d1 = Link(source_type="decision", source_id=d2.id, target_type="decision", target_id=d1.id, relation=LinkRelation.depends_on, confirmed=True)
    link_d1_d2 = Link(source_type="decision", source_id=d1.id, target_type="decision", target_id=d2.id, relation=LinkRelation.depends_on, confirmed=True)
    db.add_all([link_d2_d1, link_d1_d2])

    p1 = Premise(
        decision_id=d1.id,
        text="Underlying Premise P1",
        evidence_quote="D1",
        scope_project=project,
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
    )
    db.add(p1)
    db.flush()

    # Task T1 implementing D2
    item_t1 = Item(meeting_id=m.id, type=ItemType.action, text="Action 1", evidence_quote="A1", review_state=ReviewState.approved)
    db.add(item_t1)
    db.flush()

    t1 = Task(item_id=item_t1.id, decision_id=d2.id, title="Action 1", estimate_hours=8.0, status=TaskStatus.open)
    db.add(t1)
    db.commit()

    # Must complete in milliseconds without infinite loop
    blast = calculate_blast_radius(db, premise_id=p1.id)
    assert blast is not None
    assert len(blast["affected_decisions"]) == 2  # D1 and D2 visited exactly once
    assert len(blast["affected"]) == 1
    assert blast["affected"][0]["id"] == t1.id


def test_duplicate_task_relationships_deduplicated_in_blast_radius(db: Session):
    """
    Phase 6: When a task is connected to multiple affected decisions,
    it must appear EXACTLY ONCE in affected tasks, preventing duplicate counting.
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Deduplication Test {uid}"

    m = Meeting(title="Dedup Meeting", date=date(2026, 11, 2), project=project, transcript_ref="seed/m.vtt", status=MeetingStatus.done)
    db.add(m)
    db.flush()

    item_d1 = Item(meeting_id=m.id, type=ItemType.decision, text="D1", evidence_quote="D1", review_state=ReviewState.approved)
    item_d2 = Item(meeting_id=m.id, type=ItemType.decision, text="D2", evidence_quote="D2", review_state=ReviewState.approved)
    db.add_all([item_d1, item_d2])
    db.flush()

    d1 = Decision(item_id=item_d1.id, text="D1", scope_project=project, status=DecisionStatus.active, version=1)
    d2 = Decision(item_id=item_d2.id, text="D2", scope_project=project, status=DecisionStatus.active, version=1)
    db.add_all([d1, d2])
    db.flush()

    # D2 depends on D1
    db.add(Link(source_type="decision", source_id=d2.id, target_type="decision", target_id=d1.id, relation=LinkRelation.depends_on, confirmed=True))

    p = Premise(decision_id=d1.id, text="P1", evidence_quote="D1", scope_project=project, state=PremiseState.confirmed, status=PremiseStatus.holding)
    db.add(p)
    db.flush()

    item_t = Item(meeting_id=m.id, type=ItemType.action, text="Shared Task", evidence_quote="Shared", review_state=ReviewState.approved)
    db.add(item_t)
    db.flush()

    task_shared = Task(item_id=item_t.id, decision_id=d1.id, title="Shared Task", estimate_hours=10.0, status=TaskStatus.open)
    db.add(task_shared)
    db.flush()

    # Also link task to D2 as well via Link table
    db.add(Link(source_type="task", source_id=task_shared.id, target_type="decision", target_id=d2.id, relation=LinkRelation.implements, confirmed=True))
    db.commit()

    blast = calculate_blast_radius(db, premise_id=p.id)
    # Must appear EXACTLY ONCE
    affected_task_ids = [t["id"] for t in blast["affected"]]
    assert affected_task_ids.count(task_shared.id) == 1
    # Hours at risk counted once (10.0, not 20.0)
    assert blast["metrics"]["hours_at_risk"] == 10.0


def test_unconfirmed_links_categorized_under_needs_confirmation(db: Session):
    """
    Phase 6: Invariant 4 - Unconfirmed links (confirmed=False) must NOT be marked affected.
    They are grouped under 'needs_confirmation' ("needs confirmation, nothing changed").
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Provisional Link Test {uid}"

    m = Meeting(title="Provisional Meeting", date=date(2026, 11, 2), project=project, transcript_ref="seed/m.vtt", status=MeetingStatus.done)
    db.add(m)
    db.flush()

    item_d = Item(meeting_id=m.id, type=ItemType.decision, text="Core Decision", evidence_quote="D", review_state=ReviewState.approved)
    db.add(item_d)
    db.flush()

    d = Decision(item_id=item_d.id, text="Core Decision", scope_project=project, status=DecisionStatus.active, version=1)
    db.add(d)
    db.flush()

    p = Premise(decision_id=d.id, text="Premise", evidence_quote="D", scope_project=project, state=PremiseState.confirmed, status=PremiseStatus.holding)
    db.add(p)
    db.flush()

    item_t = Item(meeting_id=m.id, type=ItemType.action, text="Provisional Task", evidence_quote="A", review_state=ReviewState.approved)
    db.add(item_t)
    db.flush()

    t = Task(item_id=item_t.id, decision_id=None, title="Provisional Task", estimate_hours=15.0, status=TaskStatus.open)
    db.add(t)
    db.flush()

    # Link is UNCONFIRMED
    db.add(Link(source_type="task", source_id=t.id, target_type="decision", target_id=d.id, relation=LinkRelation.implements, confirmed=False))
    db.commit()

    blast = calculate_blast_radius(db, premise_id=p.id)
    # Must NOT be in affected
    assert not any(x["id"] == t.id for x in blast["affected"])
    # Must be in needs_confirmation
    assert any(x["id"] == t.id for x in blast["needs_confirmation"])
    assert blast["needs_confirmation"][0]["reason"] == "needs confirmation, nothing changed"
    # Unconfirmed task hours NOT added to hours_at_risk
    assert blast["metrics"]["hours_at_risk"] == 0.0


def test_scope_disjoint_tasks_explained_in_unaffected(db: Session):
    """
    Phase 6: Tasks in the same project with disjoint scope (e.g. Europe vs India)
    must appear in unaffected with code-generated explanation: "scope differs: Europe vs India".
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Scope Explanation Test {uid}"

    m_india = Meeting(title="India Sync", date=date(2026, 11, 2), project=project, region="India", transcript_ref="seed/m_in.vtt", status=MeetingStatus.done)
    m_europe = Meeting(title="Europe Sync", date=date(2026, 11, 2), project=project, region="Europe", transcript_ref="seed/m_eu.vtt", status=MeetingStatus.done)
    db.add_all([m_india, m_europe])
    db.flush()

    item_d = Item(meeting_id=m_india.id, type=ItemType.decision, text="India Decision", evidence_quote="D", review_state=ReviewState.approved)
    db.add(item_d)
    db.flush()

    d = Decision(item_id=item_d.id, text="India Decision", scope_project=project, scope_region="India", status=DecisionStatus.active, version=1)
    db.add(d)
    db.flush()

    p = Premise(decision_id=d.id, text="India Premise", evidence_quote="D", scope_project=project, scope_region="India", state=PremiseState.confirmed, status=PremiseStatus.holding)
    db.add(p)
    db.flush()

    item_eu_task = Item(meeting_id=m_europe.id, type=ItemType.action, text="Europe Integration", evidence_quote="EU", review_state=ReviewState.approved)
    db.add(item_eu_task)
    db.flush()

    t_europe = Task(item_id=item_eu_task.id, decision_id=None, title="Europe Integration", estimate_hours=40.0, status=TaskStatus.open)
    db.add(t_europe)
    db.commit()

    blast = calculate_blast_radius(db, premise_id=p.id)
    # Europe task is in unaffected with reason
    unaffected_eu = next((x for x in blast["unaffected"] if x["id"] == t_europe.id), None)
    assert unaffected_eu is not None
    assert "scope differs: Europe vs India" in unaffected_eu["reason"]
