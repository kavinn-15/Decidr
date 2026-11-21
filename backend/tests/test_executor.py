import uuid
from datetime import date, datetime, timezone
import pytest
import httpx
from sqlalchemy.orm import Session

from app.models.models import (
    Person,
    Meeting,
    Utterance,
    Item,
    Decision,
    Task,
    Reminder,
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
    ReminderKind,
    ReminderState,
    ReminderChannel,
)
from app.trackers.base import BaseTracker
from app.trackers.mock import MockTracker
from app.trackers.github import GitHubTracker
from app.services.executor import (
    execute_proposal,
    ProposalNotApprovedError,
)


class SpyTracker(BaseTracker):
    """
    A test spy tracker that records every method call and never makes external requests.
    """
    def __init__(self):
        self.calls = []
        self.tickets = {}
        self._counter = 0

    def create_issue(self, title, body, assignee=None, due_date=None, labels=None, idempotency_key=None):
        self.calls.append({
            "method": "create_issue",
            "title": title,
            "body": body,
            "assignee": assignee,
            "due_date": due_date,
            "labels": labels,
            "idempotency_key": idempotency_key,
        })
        if idempotency_key and idempotency_key in self.tickets:
            return self.tickets[idempotency_key]

        self._counter += 1
        ref = f"SPY-{self._counter}"
        res = {"ref": ref, "url": f"https://tracker.example.com/{ref}"}
        if idempotency_key:
            self.tickets[idempotency_key] = res
        return res

    def add_comment(self, ref, text):
        self.calls.append({"method": "add_comment", "ref": ref, "text": text})

    def reopen(self, ref):
        self.calls.append({"method": "reopen", "ref": ref})

    def cancel(self, ref):
        self.calls.append({"method": "cancel", "ref": ref})

    def find_by_key(self, idempotency_key):
        return self.tickets.get(idempotency_key, {}).get("ref")


@pytest.fixture
def base_setup(db: Session):
    """Sets up a person, meeting, item, decision, and task for executor tests."""
    uid = uuid.uuid4().hex[:6]
    person = Person(
        name="Asha",
        email=f"asha_{uid}@example.com",
        tracker_id=f"ASHA-{uid}",
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    meeting = Meeting(
        title=f"Weekly Sync {uid}",
        date=date(2026, 11, 2),
        project="Payments Revamp",
        transcript_ref=f"seed/meeting-{uid}.vtt",
        status=MeetingStatus.done,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    item = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Use Provider A for India settlements",
        evidence_quote="Let's use Provider A for India settlements",
        review_state=ReviewState.approved,
        confidence=1.0,
        needs_owner=False,
        needs_deadline=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    decision = Decision(
        item_id=item.id,
        text="Use Provider A for India settlements",
        scope_project="Payments Revamp",
        scope_region="India",
        status=DecisionStatus.active,
        version=1,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    task_item = Item(
        meeting_id=meeting.id,
        type=ItemType.action,
        text="Integrate Provider A SDK",
        evidence_quote="Ravi will integrate Provider A SDK",
        review_state=ReviewState.approved,
        confidence=1.0,
        owner_id=person.id,
        deadline=date(2026, 11, 20),
        needs_owner=False,
        needs_deadline=False,
    )
    db.add(task_item)
    db.commit()
    db.refresh(task_item)

    task = Task(
        item_id=task_item.id,
        decision_id=decision.id,
        title="Integrate Provider A SDK",
        description="Connect with Provider A settlement API",
        owner_id=person.id,
        due_date=date(2026, 11, 20),
        status=TaskStatus.open,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "person": person,
        "meeting": meeting,
        "decision": decision,
        "task": task,
    }


def test_draft_or_rejected_proposal_causes_zero_tracker_calls(db: Session, base_setup):
    """
    Safety Invariant 2: A draft or rejected proposal must raise ProposalNotApprovedError
    and cause zero tracker calls.
    """
    spy = SpyTracker()
    task = base_setup["task"]

    # 1. Draft Proposal
    draft_prop = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=1,
        summary="Draft repair proposal",
        state=ProposalState.draft,
    )
    db.add(draft_prop)
    db.commit()
    db.refresh(draft_prop)

    draft_action = ChangeAction(
        proposal_id=draft_prop.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={"title": "Draft Task"},
        idempotency_key="idemp-draft-1",
        state=ActionState.approved,
    )
    db.add(draft_action)
    db.commit()

    with pytest.raises(ProposalNotApprovedError) as exc_info:
        execute_proposal(draft_prop.id, actor="Asha", db=db, tracker=spy)
    assert "draft" in str(exc_info.value)
    assert len(spy.calls) == 0

    # 2. Rejected Proposal
    rejected_prop = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=2,
        summary="Rejected repair proposal",
        state=ProposalState.rejected,
    )
    db.add(rejected_prop)
    db.commit()
    db.refresh(rejected_prop)

    rejected_action = ChangeAction(
        proposal_id=rejected_prop.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={"title": "Rejected Task"},
        idempotency_key="idemp-rejected-1",
        state=ActionState.approved,
    )
    db.add(rejected_action)
    db.commit()

    with pytest.raises(ProposalNotApprovedError) as exc_info:
        execute_proposal(rejected_prop.id, actor="Asha", db=db, tracker=spy)
    assert "rejected" in str(exc_info.value)
    assert len(spy.calls) == 0


def test_approved_proposal_executed_twice_creates_exactly_one_ticket(db: Session, base_setup):
    """
    Safety Invariant 3: An approved proposal executed twice creates exactly 1 ticket.
    Running it twice executes nothing new (idempotent).
    """
    task = base_setup["task"]
    tracker = MockTracker(db=db)

    proposal = ChangeProposal(
        trigger_type="decision_change",
        trigger_id=1,
        summary="Create tracker ticket for integration",
        state=ProposalState.approved,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    action = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={
            "title": "Integrate Provider A SDK",
            "description": "UPI settlement implementation",
            "assignee": "ravi@example.com",
            "due_date": "2026-11-20",
        },
        idempotency_key="idemp-create-task-once",
        state=ActionState.approved,
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    # First execution
    res1 = execute_proposal(proposal.id, actor="Asha", db=db, tracker=tracker)
    assert res1["executed_count"] == 1
    assert res1["skipped_count"] == 0
    assert res1["failed_count"] == 0

    tickets = db.query(TrackerTicket).filter(TrackerTicket.idempotency_key == "idemp-create-task-once").all()
    assert len(tickets) == 1
    first_ticket_ref = tickets[0].ticket_ref
    assert first_ticket_ref.startswith("MOCK-")
    assert tickets[0].title == "Integrate Provider A SDK"

    # Verify task was updated with tracker ref
    db.refresh(task)
    assert task.tracker_ref == first_ticket_ref
    assert task.provisional is False

    # Second execution (exact same proposal executed again)
    res2 = execute_proposal(proposal.id, actor="Asha", db=db, tracker=tracker)
    assert res2["executed_count"] == 0
    assert res2["skipped_count"] == 1
    assert res2["failed_count"] == 0

    # Must still have EXACTLY 1 ticket in tracker
    tickets_after = db.query(TrackerTicket).filter(TrackerTicket.idempotency_key == "idemp-create-task-once").all()
    assert len(tickets_after) == 1
    assert tickets_after[0].ticket_ref == first_ticket_ref

    # Verify audit log recorded execution
    audit_rows = db.query(AuditLog).filter(AuditLog.entity_id == action.id).all()
    assert len(audit_rows) >= 1
    assert any(a.action == "execute_action:create_task" for a in audit_rows)


def test_failed_action_retried_without_duplicating_successful_ones(db: Session, base_setup):
    """
    Safety Verification: On error mark the action failed without losing others;
    re-running retries only failed ones without duplicating successful actions.
    """
    task = base_setup["task"]
    tracker = MockTracker(db=db)

    proposal = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=1,
        summary="Multi-action proposal with partial failure",
        state=ProposalState.approved,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    # Action 1: Create task (will succeed)
    action1 = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={"title": "Action 1 Success Task"},
        idempotency_key="idemp-action1-success",
        state=ActionState.approved,
    )
    db.add(action1)

    # Action 2: Comment on task (will fail initially because comment text is missing / or simulated failure)
    # Using an invalid target without tracker_ref causes _execute_single_action to fail
    dummy_task = Task(
        item_id=task.item_id,
        title="Unsynced Task",
        tracker_ref=None,  # No tracker ref causes comment to fail!
        status=TaskStatus.open,
    )
    db.add(dummy_task)
    db.commit()
    db.refresh(dummy_task)

    action2 = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.comment_task,
        target_type="task",
        target_id=dummy_task.id,
        payload={"text": "Alert: Premise broke on this task"},
        idempotency_key="idemp-action2-retry",
        state=ActionState.approved,
    )
    db.add(action2)
    db.commit()
    db.refresh(action1)
    db.refresh(action2)

    # 1. First Run: Action 1 succeeds, Action 2 fails
    res1 = execute_proposal(proposal.id, actor="Asha", db=db, tracker=tracker)
    assert res1["executed_count"] == 1
    assert res1["failed_count"] == 1

    db.refresh(action1)
    db.refresh(action2)
    assert action1.state == ActionState.executed
    assert action2.state == ActionState.failed
    assert "error" in (action2.result or {})

    # Only 1 ticket created for Action 1
    tickets_count = db.query(TrackerTicket).filter(TrackerTicket.idempotency_key == "idemp-action1-success").count()
    assert tickets_count == 1

    # Proposal remains approved (not fully executed yet)
    db.refresh(proposal)
    assert proposal.state == ProposalState.approved

    # 2. Fix the error for Action 2: provide a valid tracker_ref
    dummy_task.tracker_ref = action1.result["ref"]
    db.commit()

    # 3. Second Run (Retry): Action 1 is skipped; Action 2 is retried and succeeds
    res2 = execute_proposal(proposal.id, actor="Asha", db=db, tracker=tracker)
    assert res2["skipped_count"] == 1  # Action 1 was skipped
    assert res2["executed_count"] == 1  # Action 2 succeeded
    assert res2["failed_count"] == 0

    db.refresh(action1)
    db.refresh(action2)
    assert action1.state == ActionState.executed
    assert action2.state == ActionState.executed

    # Proposal is now marked executed
    db.refresh(proposal)
    assert proposal.state == ProposalState.executed

    # Ticket count is STILL 1 (Action 1 was never duplicated!)
    assert db.query(TrackerTicket).filter(TrackerTicket.idempotency_key == "idemp-action1-success").count() == 1


def test_dry_run_makes_zero_calls_and_returns_exact_payloads(db: Session, base_setup):
    """
    Safety Verification: dry_run=True makes 0 tracker calls, writes 0 mutations,
    and returns the exact payloads that would be sent.
    """
    task = base_setup["task"]
    spy = SpyTracker()

    # Add a pending reminder to task
    reminder = Reminder(
        task_id=task.id,
        kind=ReminderKind.one_day,
        due_at=datetime.now(timezone.utc),
        state=ReminderState.pending,
        channel=ReminderChannel.email,
    )
    db.add(reminder)

    proposal = ChangeProposal(
        trigger_type="premise_break",
        trigger_id=1,
        summary="Dry run test proposal",
        state=ProposalState.approved,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    action1 = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.create_task,
        target_type="task",
        target_id=task.id,
        payload={
            "title": "Dry Run Task",
            "description": "Details for dry run",
            "assignee": "ravi@example.com",
            "due_date": "2026-11-20",
        },
        idempotency_key="idemp-dryrun-1",
        state=ActionState.approved,
    )
    action2 = ChangeAction(
        proposal_id=proposal.id,
        action_type=ActionType.pause_reminders,
        target_type="task",
        target_id=task.id,
        payload={"reason": "Premise broken"},
        idempotency_key="idemp-dryrun-2",
        state=ActionState.approved,
    )
    db.add_all([action1, action2])
    db.commit()

    # Execute with dry_run=True
    audit_count_before = db.query(AuditLog).count()
    result = execute_proposal(proposal.id, actor="Asha", dry_run=True, db=db, tracker=spy)

    assert result["dry_run"] is True
    assert result["executed_count"] == 0
    assert len(spy.calls) == 0  # Zero tracker calls
    assert len(result["planned_actions"]) == 2

    # Check exact payloads
    p1 = result["planned_actions"][0]["payload"]
    assert p1["type"] == "tracker.create_issue"
    assert p1["title"] == "Dry Run Task"
    assert p1["assignee"] == "ravi@example.com"
    assert p1["idempotency_key"] == "idemp-dryrun-1"

    p2 = result["planned_actions"][1]["payload"]
    assert p2["type"] == "local.pause_reminders"
    assert p2["task_id"] == task.id
    assert p2["idempotency_key"] == "idemp-dryrun-2"

    # State unchanged
    db.refresh(proposal)
    db.refresh(action1)
    db.refresh(action2)
    db.refresh(reminder)
    assert proposal.state == ProposalState.approved
    assert action1.state == ActionState.approved
    assert action2.state == ActionState.approved
    assert reminder.state == ReminderState.pending

    # Zero audit log rows written
    audit_count_after = db.query(AuditLog).count()
    assert audit_count_after == audit_count_before


def test_github_tracker_with_mock_client():
    """
    Tests GitHubTracker:
    - embeds `<!-- decidr:KEY -->` in the issue body
    - uses label 'decidr'
    - find_by_key locates issue by embedded key
    - idempotency returns existing issue
    """
    mock_issues = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if request.method == "POST" and url.endswith("/repos/test-org/test-repo/issues"):
            import json
            data = json.loads(request.content.decode("utf-8"))
            num = len(mock_issues) + 1
            issue = {
                "number": num,
                "title": data.get("title"),
                "body": data.get("body"),
                "labels": [{"name": l} for l in data.get("labels", [])],
                "html_url": f"https://github.com/test-org/test-repo/issues/{num}",
            }
            mock_issues.append(issue)
            return httpx.Response(201, json=issue)

        if request.method == "GET" and "/repos/test-org/test-repo/issues" in url:
            return httpx.Response(200, json=mock_issues)

        if request.method == "GET" and "/search/issues" in url:
            return httpx.Response(200, json={"items": mock_issues})

        if request.method == "POST" and "/comments" in url:
            return httpx.Response(201, json={"id": 123})

        if request.method == "PATCH":
            return httpx.Response(200, json={"state": "open"})

        return httpx.Response(404, json={"message": "Not Found"})

    client = httpx.Client(
        transport=httpx.MockTransport(mock_handler),
        base_url="https://api.github.com",
    )

    tracker = GitHubTracker(token="dummy-token", repo="test-org/test-repo", client=client)

    # 1. Create issue
    res1 = tracker.create_issue(
        title="UPI Integration Issue",
        body="Must implement T+0 settlement",
        due_date="2026-11-20",
        idempotency_key="idemp-gh-test-1",
    )
    assert res1["ref"] == "1"
    assert "1" in res1["url"]

    # Verify key was embedded in body
    assert len(mock_issues) == 1
    created_body = mock_issues[0]["body"]
    assert "<!-- decidr:idemp-gh-test-1 -->" in created_body
    labels = [l["name"] for l in mock_issues[0]["labels"]]
    assert "decidr" in labels

    # 2. find_by_key locates issue
    found_ref = tracker.find_by_key("idemp-gh-test-1")
    assert found_ref == "1"

    # 3. Idempotent create_issue returns existing issue without making a new one
    res2 = tracker.create_issue(
        title="Duplicate Issue Call",
        body="Another body",
        idempotency_key="idemp-gh-test-1",
    )
    assert res2["ref"] == "1"
    assert len(mock_issues) == 1  # No duplicate issue was created!


def test_mock_tracker_ui_and_api(client, db: Session):
    """
    Tests GET /mock-tracker (HTML UI) and GET /api/mock-tracker/tickets (JSON API).
    """
    tracker = MockTracker(db=db)
    res = tracker.create_issue(
        title="UI Test Ticket",
        body="This ticket tests the UI render",
        assignee="Asha",
        due_date="2026-11-25",
        labels=["decidr", "payments"],
        idempotency_key="idemp-ui-ticket-1",
    )
    tracker.add_comment(res["ref"], "First update on ticket")

    # 1. HTML Endpoint
    html_resp = client.get("/mock-tracker")
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers["content-type"]
    assert "Decidr Mock Issue Tracker" in html_resp.text
    assert "UI Test Ticket" in html_resp.text
    assert "First update on ticket" in html_resp.text
    assert "MOCK-1" in html_resp.text

    # 2. JSON Endpoint
    json_resp = client.get("/api/mock-tracker/tickets")
    assert json_resp.status_code == 200
    data = json_resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["ticket_ref"] == res["ref"]
    assert data[0]["title"] == "UI Test Ticket"
    assert len(data[0]["comments"]) == 1
