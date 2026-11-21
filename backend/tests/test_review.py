import uuid
from datetime import date, datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.models import (
    Person,
    Meeting,
    Utterance,
    Item,
    Decision,
    DecisionVersion,
    Premise,
    Task,
    Link,
    Alert,
    TrackerTicket,
    AuditLog,
)
from app.models.enums import (
    MeetingStatus,
    ItemType,
    ReviewState,
    DecisionStatus,
    PremiseState,
    PremiseStatus,
    TaskStatus,
    AlertKind,
    AlertState,
    LinkRelation,
)


@pytest.fixture
def review_setup(db: Session):
    uid = uuid.uuid4().hex[:6]
    person = Person(name="Asha", email=f"asha_{uid}@example.com", tracker_id=f"ASHA-{uid}")
    db.add(person)
    db.commit()
    db.refresh(person)

    meeting = Meeting(
        title=f"Review Meeting {uid}",
        date=date(2026, 11, 2),
        project="Payments Revamp",
        region="India",
        release="v1.0",
        transcript_ref=f"seed/meeting-{uid}.vtt",
        status=MeetingStatus.review,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    utt1 = Utterance(
        meeting_id=meeting.id,
        idx=0,
        speaker_raw="Asha",
        person_id=person.id,
        text="We will use Provider A for India settlements.",
    )
    utt2 = Utterance(
        meeting_id=meeting.id,
        idx=1,
        speaker_raw="Asha",
        person_id=person.id,
        text="Provider A supports T+0 UPI settlement.",
    )
    utt3 = Utterance(
        meeting_id=meeting.id,
        idx=2,
        speaker_raw="Ravi",
        person_id=person.id,
        text="Ravi will integrate Provider A SDK by Nov 20.",
    )
    db.add_all([utt1, utt2, utt3])
    db.commit()
    db.refresh(utt1)
    db.refresh(utt2)
    db.refresh(utt3)

    # 1. Decision item
    dec_item = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Use Provider A for India settlements",
        evidence_quote="We will use Provider A for India settlements.",
        utterance_id=utt1.id,
        review_state=ReviewState.proposed,
        confidence=0.98,
        needs_owner=False,
        needs_deadline=False,
    )
    db.add(dec_item)
    db.commit()
    db.refresh(dec_item)

    decision = Decision(
        item_id=dec_item.id,
        text="Use Provider A for India settlements",
        scope_project="Payments Revamp",
        scope_region="India",
        scope_release="v1.0",
        effective_from=meeting.date,
        status=DecisionStatus.active,
        version=1,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    # 2. Premise
    premise = Premise(
        decision_id=decision.id,
        text="Provider A supports T+0 UPI settlement",
        evidence_quote="Provider A supports T+0 UPI settlement.",
        utterance_id=utt2.id,
        scope_project="Payments Revamp",
        scope_region="India",
        valid_from=meeting.date,
        state=PremiseState.proposed,
        status=PremiseStatus.holding,
    )
    db.add(premise)
    db.commit()
    db.refresh(premise)

    # 3. Action item
    action_item = Item(
        meeting_id=meeting.id,
        type=ItemType.action,
        text="Integrate Provider A SDK",
        evidence_quote="Ravi will integrate Provider A SDK by Nov 20.",
        utterance_id=utt3.id,
        owner_id=person.id,
        deadline=date(2026, 11, 20),
        review_state=ReviewState.proposed,
        confidence=0.95,
        needs_owner=False,
        needs_deadline=False,
    )
    db.add(action_item)
    db.commit()
    db.refresh(action_item)

    task = Task(
        item_id=action_item.id,
        decision_id=decision.id,
        title="Integrate Provider A SDK",
        description="Integrate Provider A SDK for UPI settlement",
        owner_id=person.id,
        due_date=date(2026, 11, 20),
        provisional=True,
        status=TaskStatus.open,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 4. Link
    link = Link(
        source_type="task",
        source_id=task.id,
        target_type="decision",
        target_id=decision.id,
        relation=LinkRelation.implements,
        confirmed=False,
        confidence=0.55,
        rationale="Low confidence link candidate",
    )
    db.add(link)

    # 5. Alert
    alert = Alert(
        kind=AlertKind.premise_break,
        meeting_id=meeting.id,
        utterance_id=utt2.id,
        premise_id=premise.id,
        decision_id=decision.id,
        verdict="Contradiction",
        old_quote="Provider A supports T+0 UPI settlement.",
        new_quote="Provider A only supports T+2 settlement.",
        explanation="Settlement speed premise broke",
        state=AlertState.open,
    )
    db.add(alert)
    db.commit()
    db.refresh(link)
    db.refresh(alert)

    return {
        "person": person,
        "meeting": meeting,
        "dec_item": dec_item,
        "decision": decision,
        "premise": premise,
        "action_item": action_item,
        "task": task,
        "link": link,
        "alert": alert,
    }


def test_get_meeting_review_returns_ordered_cards(client, review_setup):
    """
    Tests GET /meetings/{id}/review returns cards in proper order:
    alerts first, then decisions with nested premises, then actions, then links.
    """
    meeting_id = review_setup["meeting"].id
    resp = client.get(f"/meetings/{meeting_id}/review")
    assert resp.status_code == 200
    data = resp.json()

    assert data["meeting_id"] == meeting_id
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["kind"] == "premise_break"

    assert len(data["decisions"]) == 1
    decision = data["decisions"][0]
    assert decision["text"] == "Use Provider A for India settlements"
    assert len(decision["premises"]) == 1
    assert decision["premises"][0]["text"] == "Provider A supports T+0 UPI settlement"

    assert len(data["actions"]) == 1
    assert data["actions"][0]["text"] == "Integrate Provider A SDK"

    assert len(data["links"]) == 1
    assert data["links"][0]["confidence"] == 0.55


def test_approving_action_creates_exactly_one_ticket(client, db: Session, review_setup):
    """
    Safety Verification: Approving an action creates a task and an approved create_task
    change_action, runs the executor, and creates exactly 1 ticket in the tracker.
    When all premises are confirmed, provisional is False.
    """
    action_item = review_setup["action_item"]
    premise = review_setup["premise"]

    # Confirm the premise first
    premise.state = PremiseState.confirmed
    premise.status = PremiseStatus.holding
    db.commit()

    # Initial tracker ticket count for this item
    tickets_before = db.query(TrackerTicket).count()

    # Approve the action
    resp = client.post(
        f"/review/actions/{action_item.id}/approve",
        json={"actor": "Meera", "approve_unassigned": False},
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "approved"
    assert res_data["provisional"] is False
    assert res_data["tracker_ref"].startswith("MOCK-")

    # Exactly 1 new ticket was created
    tickets_after = db.query(TrackerTicket).count()
    assert tickets_after == tickets_before + 1

    # Check task provisional is False
    task = db.get(Task, res_data["task_id"])
    assert task.provisional is False
    assert task.tracker_ref == res_data["tracker_ref"]

    # Verify audit log row exists
    audit_entry = (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == action_item.id, AuditLog.action == "approve_action")
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.actor == "Meera"


def test_action_with_unconfirmed_premise_sets_provisional(client, db: Session, review_setup):
    """
    Invariant 4: If any premise of the linked decision is unconfirmed,
    the task is created with provisional=true and the ticket gets the provisional label
    and 'Rests on an unverified premise' in its body.
    """
    action_item = review_setup["action_item"]
    premise = review_setup["premise"]

    # Premise is unconfirmed (proposed)
    assert premise.state == PremiseState.proposed

    resp = client.post(
        f"/review/actions/{action_item.id}/approve",
        json={"actor": "Asha", "approve_unassigned": True},
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["provisional"] is True

    # Check ticket has label and notice
    ticket = (
        db.query(TrackerTicket)
        .filter(TrackerTicket.ticket_ref == res_data["tracker_ref"])
        .first()
    )
    assert ticket is not None
    assert "provisional" in ticket.labels
    assert "Rests on an unverified premise" in ticket.body


def test_rejecting_action_calls_nothing(client, db: Session, review_setup):
    """
    Safety Invariant 2: Rejecting an action creates zero tracker tickets and makes no external calls.
    """
    action_item = review_setup["action_item"]
    tickets_before = db.query(TrackerTicket).count()

    resp = client.post(
        f"/review/actions/{action_item.id}/reject",
        json={"actor": "Karthik"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    db.refresh(action_item)
    assert action_item.review_state == ReviewState.rejected
    if action_item.task:
        assert action_item.task.status == TaskStatus.cancelled

    # Zero tickets created
    assert db.query(TrackerTicket).count() == tickets_before

    # Audit log recorded rejection
    audit_entry = (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == action_item.id, AuditLog.action == "reject_action")
        .first()
    )
    assert audit_entry is not None


def test_action_missing_owner_or_deadline_requires_unassigned_choice(client, db: Session, review_setup):
    """
    Invariant 1: An action with missing owner or deadline can be approved ONLY
    after the reviewer fills the field or explicitly chooses 'approve unassigned'.
    """
    action_item = review_setup["action_item"]
    # Clear owner and deadline
    action_item.owner_id = None
    action_item.deadline = None
    action_item.needs_owner = True
    action_item.needs_deadline = True
    db.commit()

    # 1. Attempting to approve without fields and without approve_unassigned fails
    resp = client.post(
        f"/review/actions/{action_item.id}/approve",
        json={"actor": "Asha", "approve_unassigned": False},
    )
    assert resp.status_code == 400
    assert "owner and deadline" in resp.json()["detail"]

    # 2. Approving with approve_unassigned=True succeeds
    resp2 = client.post(
        f"/review/actions/{action_item.id}/approve",
        json={"actor": "Asha", "approve_unassigned": True},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "approved"


def test_approving_decision_creates_decision_and_version(client, db: Session, review_setup):
    """
    Rule: Approving a decision creates the decisions row plus a decision_versions row.
    """
    dec_item = review_setup["dec_item"]
    dec_item.review_state = ReviewState.proposed
    db.commit()

    resp = client.post(
        f"/review/decisions/{dec_item.id}/approve",
        json={"actor": "Asha"},
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "approved"

    # Verify decision_versions row exists
    version = (
        db.query(DecisionVersion)
        .filter_by(decision_id=res_data["decision_id"], version=1)
        .first()
    )
    assert version is not None
    assert version.changed_by == "Asha"


def test_approving_and_rejecting_premise(client, db: Session, review_setup):
    """
    Rule: Approving a premise sets state=confirmed and status=holding;
    rejecting a premise sets state=rejected.
    """
    premise = review_setup["premise"]

    # 1. Approve
    resp = client.post(
        f"/review/premises/{premise.id}/approve",
        json={"actor": "Asha"},
    )
    assert resp.status_code == 200
    db.refresh(premise)
    assert premise.state == PremiseState.confirmed
    assert premise.status == PremiseStatus.holding
    assert premise.confirmed_by == "Asha"

    # 2. Reject
    resp2 = client.post(
        f"/review/premises/{premise.id}/reject",
        json={"actor": "Meera"},
    )
    assert resp2.status_code == 200
    db.refresh(premise)
    assert premise.state == PremiseState.rejected
