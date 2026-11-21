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


def test_mixed_estimation_units_and_unestimated_tasks(db: Session):
    """
    Phase 7: Zombie-Work Cost Calculation
    Verify:
    - Hours
    - Story points
    - Missing estimates
    - Mixed estimation units
    - Invariant 10: Never guess an estimate
    """
    uid = uuid.uuid4().hex[:6]
    project = f"Cost Test {uid}"

    m = Meeting(title="Cost Meeting", date=date(2026, 11, 2), project=project, transcript_ref="seed/m.vtt", status=MeetingStatus.done)
    db.add(m)
    db.flush()

    item_d = Item(meeting_id=m.id, type=ItemType.decision, text="Cost Decision", evidence_quote="D", review_state=ReviewState.approved)
    db.add(item_d)
    db.flush()

    d = Decision(item_id=item_d.id, text="Cost Decision", scope_project=project, status=DecisionStatus.active, version=1)
    db.add(d)
    db.flush()

    p = Premise(decision_id=d.id, text="Cost Premise", evidence_quote="D", scope_project=project, state=PremiseState.confirmed, status=PremiseStatus.holding)
    db.add(p)
    db.flush()

    # Task 1: 18.5 hours
    it1 = Item(meeting_id=m.id, type=ItemType.action, text="Task with Hours", evidence_quote="T1", review_state=ReviewState.approved)
    db.add(it1)
    db.flush()
    t1 = Task(item_id=it1.id, decision_id=d.id, title="Task with Hours", estimate_hours=18.5, estimate_points=None, status=TaskStatus.open)

    # Task 2: 8.0 story points
    it2 = Item(meeting_id=m.id, type=ItemType.action, text="Task with Story Points", evidence_quote="T2", review_state=ReviewState.approved)
    db.add(it2)
    db.flush()
    t2 = Task(item_id=it2.id, decision_id=d.id, title="Task with Story Points", estimate_hours=None, estimate_points=8.0, status=TaskStatus.open)

    # Task 3: Unestimated task (estimate is None)
    it3 = Item(meeting_id=m.id, type=ItemType.action, text="Unestimated Task", evidence_quote="T3", review_state=ReviewState.approved)
    db.add(it3)
    db.flush()
    t3 = Task(item_id=it3.id, decision_id=d.id, title="Unestimated Task", estimate_hours=None, estimate_points=None, status=TaskStatus.open)

    # Task 4: Done task (should NOT be added to open hours at risk)
    it4 = Item(meeting_id=m.id, type=ItemType.action, text="Done Task", evidence_quote="T4", review_state=ReviewState.approved)
    db.add(it4)
    db.flush()
    t4 = Task(item_id=it4.id, decision_id=d.id, title="Done Task", estimate_hours=12.0, estimate_points=None, status=TaskStatus.done)

    db.add_all([t1, t2, t3, t4])
    db.commit()

    blast = calculate_blast_radius(db, premise_id=p.id)
    metrics = blast["metrics"]

    # Invariant 10: Exact measured values
    assert metrics["hours_at_risk"] == 18.5  # Only open task t1 (t4 done is excluded)
    assert metrics["points_at_risk"] == 8.0  # Only open task t2
    assert metrics["unestimated_count"] == 1  # Only open task t3

    # Explanation summary covers mixed units
    summary = metrics["effort_summary"]
    assert "18.5 hours" in summary
    assert "8.0 story points" in summary
    assert "1 tasks without estimate" in summary
