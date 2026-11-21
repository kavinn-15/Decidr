import uuid
from datetime import date, datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, init_db, engine
from app.models.models import (
    Person,
    Meeting,
    Item,
    Decision,
    Task,
    ChangeProposal,
    ChangeAction,
    TrackerTicket,
    AuditLog,
)
from app.models.enums import (
    MeetingStatus,
    ItemType,
    ReviewState,
    DecisionStatus,
    TaskStatus,
    ProposalState,
    ActionType,
    ActionState,
)
from app.trackers.base import BaseTracker
from app.trackers.mock import MockTracker
from app.services.executor import execute_proposal, ProposalNotApprovedError


@pytest.fixture
def db():
    init_db(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def repair_setup(db: Session):
    uid = uuid.uuid4().hex[:6]
    person = Person(name="Engineer", email=f"eng_{uid}@example.com", tracker_id=f"ENG-{uid}")
    db.add(person)
    db.flush()

    meeting = Meeting(
        title="Sprint Sync",
        date=date(2026, 11, 2),
        project="Core Engine",
        transcript_ref="seed/m.vtt",
        status=MeetingStatus.done,
    )
    db.add(meeting)
    db.flush()

    item_d = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Use RabbitMQ for event bus",
        evidence_quote="RabbitMQ for event bus",
        review_state=ReviewState.approved,
    )
    db.add(item_d)
    db.flush()

    d = Decision(
        item_id=item_d.id,
        text="Use RabbitMQ for event bus",
        scope_project="Core Engine",
        status=DecisionStatus.active,
        version=1,
    )
    db.add(d)
    db.flush()

    item_t = Item(
        meeting_id=meeting.id,
        type=ItemType.action,
        text="Deploy RabbitMQ cluster",
        evidence_quote="Deploy RabbitMQ cluster",
        review_state=ReviewState.approved,
    )
    db.add(item_t)
    db.flush()

    task = Task(
        item_id=item_t.id,
        decision_id=d.id,
        title="Deploy RabbitMQ cluster",
        owner_id=person.id,
        status=TaskStatus.open,
        estimate_hours=12.0,
    )
    db.add(task)
    db.commit()

    return {
        "person": person,
        "meeting": meeting,
        "decision": d,
        "task": task,
    }


def test_approved_repair_executes_successfully(db: Session, repair_setup):
    """
    Test 1: Approved repair executes properly, creates tracker ticket, and logs audit row.
    """
    task = repair_setup["task"]
    tracker = MockTracker(db=db)

    proposal = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=10,
        summary="Approved Repair Plan",
        state=ProposalState.approved,
    )
    db.add(proposal)
    db.flush()

    action = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={"title": "Deploy RabbitMQ cluster", "description": "High availability"},
        idempotency_key="idemp-approved-1",
        state=ActionState.approved,
    )
    db.add(action)
    db.commit()

    res = execute_proposal(proposal.id, actor="Lead", db=db, tracker=tracker)
    assert res["executed_count"] == 1
    assert res["skipped_count"] == 0
    assert res["failed_count"] == 0

    db.refresh(action)
    assert action.state == ActionState.executed
    assert action.result["ref"].startswith("MOCK-")

    # Invariant 7: Audit log row written
    audit_row = db.query(AuditLog).filter(AuditLog.entity_id == action.id).first()
    assert audit_row is not None
    assert audit_row.action == "execute_action:create_task"


def test_rejected_repair_creates_zero_external_writes(db: Session, repair_setup):
    """
    Test 2: Rejected repair raises ProposalNotApprovedError and creates ZERO external writes.
    """
    task = repair_setup["task"]
    tracker = MockTracker(db=db)

    proposal = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=11,
        summary="Rejected Repair Plan",
        state=ProposalState.rejected,  # REJECTED!
    )
    db.add(proposal)
    db.flush()

    action = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={"title": "Unauthorized Task"},
        idempotency_key="idemp-rejected-writes-0",
        state=ActionState.approved,
    )
    db.add(action)
    db.commit()

    with pytest.raises(ProposalNotApprovedError):
        execute_proposal(proposal.id, actor="Lead", db=db, tracker=tracker)

    # Assert ZERO tracker tickets created
    assert db.query(TrackerTicket).filter(TrackerTicket.idempotency_key == "idemp-rejected-writes-0").count() == 0


def test_double_click_and_repeated_execution_is_idempotent(db: Session, repair_setup):
    """
    Tests 3 & 4: Repeated execution / double-click execution runs without creating duplicate tasks.
    """
    task = repair_setup["task"]
    tracker = MockTracker(db=db)

    proposal = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=12,
        summary="Double Click Test",
        state=ProposalState.approved,
    )
    db.add(proposal)
    db.flush()

    action = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={"title": "Single Instance Task"},
        idempotency_key="idemp-double-click-safe",
        state=ActionState.approved,
    )
    db.add(action)
    db.commit()

    # First click
    res1 = execute_proposal(proposal.id, actor="Lead", db=db, tracker=tracker)
    assert res1["executed_count"] == 1

    # Second click (double-click immediately afterwards)
    res2 = execute_proposal(proposal.id, actor="Lead", db=db, tracker=tracker)
    assert res2["executed_count"] == 0
    assert res2["skipped_count"] == 1  # Action safely skipped

    # Exactly 1 ticket created
    tickets = db.query(TrackerTicket).filter(TrackerTicket.idempotency_key == "idemp-double-click-safe").all()
    assert len(tickets) == 1


class FailingTracker(BaseTracker):
    """Simulates transient network or server errors."""
    def __init__(self, fail_first_n_times=1):
        self.fail_count = fail_first_n_times
        self.attempts = 0

    def create_issue(self, title, body, assignee=None, due_date=None, labels=None, idempotency_key=None):
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise ConnectionError("Network connection reset by peer during tracker POST /issues")
        return {"ref": f"RETRY-OK-{self.attempts}", "url": f"https://tracker.local/{self.attempts}"}

    def add_comment(self, ref, text):
        pass

    def reopen(self, ref):
        pass

    def cancel(self, ref):
        pass

    def find_by_key(self, idempotency_key):
        return None


def test_network_failure_marks_failed_and_retry_succeeds(db: Session, repair_setup):
    """
    Tests 6 & 7: Network failure during execution marks action failed without corrupting state.
    Retry succeeds and does not falsely report success during failure.
    """
    task = repair_setup["task"]
    flaky_tracker = FailingTracker(fail_first_n_times=1)

    proposal = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=13,
        summary="Network Failure Test",
        state=ProposalState.approved,
    )
    db.add(proposal)
    db.flush()

    action = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={"title": "Resilient Task"},
        idempotency_key="idemp-network-retry-safe",
        state=ActionState.approved,
    )
    db.add(action)
    db.commit()

    # Attempt 1: Fails due to network error
    res1 = execute_proposal(proposal.id, actor="Lead", db=db, tracker=flaky_tracker)
    assert res1["failed_count"] == 1
    assert res1["executed_count"] == 0

    db.refresh(action)
    assert action.state == ActionState.failed
    assert "Network connection reset" in action.result.get("error", "")

    # Proposal remains approved, allowing retry
    db.refresh(proposal)
    assert proposal.state == ProposalState.approved

    # Attempt 2 (Retry): Succeeds cleanly
    res2 = execute_proposal(proposal.id, actor="Lead", db=db, tracker=flaky_tracker)
    assert res2["executed_count"] == 1
    assert res2["failed_count"] == 0

    db.refresh(action)
    assert action.state == ActionState.executed
    assert action.result["ref"].startswith("RETRY-OK")
    db.refresh(proposal)
    assert proposal.state == ProposalState.executed
