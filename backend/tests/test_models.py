from datetime import date, datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update, delete

from app.models.models import (
    Person,
    Meeting,
    Utterance,
    Item,
    Decision,
    DecisionVersion,
    Premise,
    Link,
    Task,
    Alert,
    ChangeProposal,
    ChangeAction,
    Reminder,
    Outbox,
    AuditLog,
    ReadOnlyAuditLogError,
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
    ActionState,
    ReminderKind,
    ReminderState,
    ReminderChannel,
)
from app.services.audit import log


def test_chain_creation(db):
    """
    Test creating the full chain:
    meeting > utterance > item > decision > premise > task > links
    """
    # 1. Person
    alice = Person(
        name="Alice Smith",
        email="alice@example.com",
        tracker_id="ALICE-1",
        slack_id="U12345",
    )
    db.add(alice)
    db.commit()
    db.refresh(alice)
    assert alice.id is not None

    # 2. Meeting
    meeting = Meeting(
        title="Sprint Architecture Planning",
        date=date(2026, 11, 21),
        project="Checkout",
        region="India",
        release="v1.0",
        transcript_ref="s3://transcripts/meeting-1.vtt",
        status=MeetingStatus.uploaded,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    assert meeting.id is not None

    # 3. Utterance
    utterance = Utterance(
        meeting_id=meeting.id,
        idx=0,
        speaker_raw="Alice Smith",
        person_id=alice.id,
        text="We have decided to use Stripe for payment processing in India.",
        start_ts=12.5,
    )
    db.add(utterance)
    db.commit()
    db.refresh(utterance)
    assert utterance.id is not None

    # 4. Item
    item = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Use Stripe for payment processing in India",
        owner_id=alice.id,
        deadline=date(2026, 12, 1),
        needs_owner=False,
        needs_deadline=False,
        confidence=0.98,
        evidence_quote="We have decided to use Stripe for payment processing in India.",
        utterance_id=utterance.id,
        review_state=ReviewState.proposed,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.id is not None

    # 5. Decision
    decision = Decision(
        item_id=item.id,
        text="Use Stripe for payment processing",
        scope_project="Checkout",
        scope_region="India",
        scope_release="v1.0",
        effective_from=date(2026, 11, 21),
        effective_to=None,
        status=DecisionStatus.active,
        version=1,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    assert decision.id is not None

    # 6. Premise
    premise = Premise(
        decision_id=decision.id,
        text="Stripe supports required Indian settlement flows",
        evidence_quote="We have decided to use Stripe for payment processing in India.",
        utterance_id=utterance.id,
        scope_project="Checkout",
        scope_region="India",
        valid_from=date(2026, 11, 21),
        state=PremiseState.confirmed,
        status=PremiseStatus.holding,
        confirmed_by="Alice Smith",
    )
    db.add(premise)
    db.commit()
    db.refresh(premise)
    assert premise.id is not None

    # 7. Task
    task_item = Item(
        meeting_id=meeting.id,
        type=ItemType.action,
        text="Implement Stripe webhook handlers",
        owner_id=alice.id,
        deadline=date(2026, 11, 30),
        needs_owner=False,
        needs_deadline=False,
        confidence=0.95,
        evidence_quote="We have decided to use Stripe for payment processing in India.",
        utterance_id=utterance.id,
        review_state=ReviewState.proposed,
    )
    db.add(task_item)
    db.commit()
    db.refresh(task_item)

    task = Task(
        item_id=task_item.id,
        decision_id=decision.id,
        title="Implement Stripe webhook handlers",
        description="Integrate Stripe webhooks for instant payment notifications",
        owner_id=alice.id,
        due_date=date(2026, 11, 30),
        estimate_hours=16.0,
        provisional=True,
        status=TaskStatus.open,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    assert task.id is not None

    # 8. Link
    link = Link(
        source_type="task",
        source_id=task.id,
        target_type="decision",
        target_id=decision.id,
        relation=LinkRelation.implements,
        confirmed=True,
        confidence=1.0,
        rationale="Webhook task directly implements the payment processor decision",
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    assert link.id is not None
    assert link.relation == LinkRelation.implements

    # Verify query traversals
    fetched_decision = db.execute(select(Decision).where(Decision.id == decision.id)).scalar_one()
    assert len(fetched_decision.premises) == 1
    assert fetched_decision.premises[0].text == "Stripe supports required Indian settlement flows"
    assert len(fetched_decision.tasks) == 1
    assert fetched_decision.tasks[0].title == "Implement Stripe webhook handlers"


def test_foreign_keys_enforced(db):
    """
    Assert SQLite foreign key constraints are strictly enforced.
    """
    # Inserting an utterance with a non-existent meeting_id must fail
    invalid_utterance = Utterance(
        meeting_id=999999,
        idx=0,
        speaker_raw="Ghost",
        text="Should fail foreign key",
    )
    db.add(invalid_utterance)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Inserting an item with a non-existent meeting_id must fail
    invalid_item = Item(
        meeting_id=999999,
        type=ItemType.decision,
        text="Invalid meeting item",
        evidence_quote="quote",
    )
    db.add(invalid_item)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Inserting a task with non-existent item_id must fail
    invalid_task = Task(
        item_id=999999,
        title="Orphan task",
    )
    db.add(invalid_task)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_audit_log_append_only(db):
    """
    Assert audit_log is strictly append-only:
    UPDATE and DELETE operations must raise ReadOnlyAuditLogError.
    """
    entry = log(
        actor="reviewer@decidr.ai",
        action="approve_decision",
        entity_type="decision",
        entity_id=1,
        before={"status": "proposed"},
        after={"status": "approved"},
        db=db,
    )
    db.commit()
    db.refresh(entry)
    entry_id = entry.id
    assert entry_id is not None
    assert entry.action == "approve_decision"

    # Attempt to update via ORM instance must raise
    entry.action = "tampered_action"
    with pytest.raises(ReadOnlyAuditLogError):
        db.commit()
    db.rollback()

    # Attempt to delete via ORM instance must raise
    record_to_delete = db.execute(select(AuditLog).where(AuditLog.id == entry_id)).scalar_one()
    db.delete(record_to_delete)
    with pytest.raises(ReadOnlyAuditLogError):
        db.commit()
    db.rollback()

    # Attempt to bulk update via execute must raise
    with pytest.raises(ReadOnlyAuditLogError):
        db.execute(
            update(AuditLog)
            .where(AuditLog.id == entry_id)
            .values(action="bulk_tampered")
        )

    # Attempt to bulk delete via execute must raise
    with pytest.raises(ReadOnlyAuditLogError):
        db.execute(
            delete(AuditLog).where(AuditLog.id == entry_id)
        )
