import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal, init_db, engine
from app.models.models import (
    Person,
    Meeting,
    Utterance,
    Item,
    Decision,
    Premise,
    Task,
    Link,
    Alert,
    ChangeProposal,
    ChangeAction,
    Reminder,
    TrackerTicket,
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
)
from app.services.repair import generate_repair_plan, make_idempotency_key
from app.services.executor import execute_proposal, ProposalNotApprovedError


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.TRACKER = "mock"
    settings.LLM_PROVIDER = "fake"
    settings.LLM_MODE = "live"
    init_db(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def p1_break_scenario():
    """
    Seeds M1 and M2 scenario where P1 (T+0 settlement) breaks due to Sam's remark in M2.
    """
    with SessionLocal() as db:
        uid = uuid.uuid4().hex[:6]

        ravi = Person(name="Ravi", email=f"ravi_{uid}@example.com", tracker_id=f"ravi_{uid}")
        meera = Person(name="Meera", email=f"meera_{uid}@example.com", tracker_id=f"meera_{uid}")
        karthik = Person(name="Karthik", email=f"karthik_{uid}@example.com", tracker_id=f"karthik_{uid}")
        sam = Person(name="Sam", email=f"sam_{uid}@example.com", tracker_id=f"sam_{uid}")
        db.add_all([ravi, meera, karthik, sam])
        db.flush()

        # Meeting 1
        m1 = Meeting(
            title="Meeting 1",
            date=date(2026, 11, 2),
            project="Payments Revamp",
            region="India",
            transcript_ref="m1.vtt",
            status=MeetingStatus.done,
        )
        db.add(m1)
        db.flush()

        # Decisions
        item_d1 = Item(
            meeting_id=m1.id,
            type=ItemType.decision,
            text="Use Provider A for India settlements",
            review_state=ReviewState.approved,
            evidence_quote="we will use Provider A for India settlements.",
        )
        db.add(item_d1)
        db.flush()

        d1 = Decision(
            item_id=item_d1.id,
            text=item_d1.text,
            scope_project="Payments Revamp",
            scope_region="India",
            effective_from=date(2026, 11, 2),
            status=DecisionStatus.active,
            version=1,
        )
        db.add(d1)
        db.flush()

        # Premise P1
        p1 = Premise(
            decision_id=d1.id,
            text="Provider A supports T+0 UPI settlement",
            evidence_quote="Provider A supports T+0 UPI settlement",
            scope_project="Payments Revamp",
            scope_region="India",
            state=PremiseState.confirmed,
            status=PremiseStatus.holding,
        )
        db.add(p1)
        db.flush()

        # Tasks linked to D1
        # T1 (with tracker ticket)
        item_t1 = Item(meeting_id=m1.id, type=ItemType.action, text="Integrate Provider A SDK", review_state=ReviewState.approved, evidence_quote="integrate Provider A SDK")
        db.add(item_t1)
        db.flush()
        t1 = Task(item_id=item_t1.id, decision_id=d1.id, title="Integrate Provider A SDK", owner_id=ravi.id, due_date=date(2026, 11, 20), tracker_ref=f"MOCK-T1-{uid}", tracker_url=f"http://mock/t1-{uid}", status=TaskStatus.open, provisional=False, estimate_hours=20.0)
        db.add(t1)

        # T2 (with tracker ticket)
        item_t2 = Item(meeting_id=m1.id, type=ItemType.action, text="Build settlement reconciliation screen", review_state=ReviewState.approved, evidence_quote="build settlement reconciliation screen")
        db.add(item_t2)
        db.flush()
        t2 = Task(item_id=item_t2.id, decision_id=d1.id, title="Build settlement reconciliation screen", owner_id=meera.id, tracker_ref=f"MOCK-T2-{uid}", tracker_url=f"http://mock/t2-{uid}", status=TaskStatus.open, provisional=False, estimate_hours=15.0)
        db.add(t2)

        # T3 (without tracker ticket)
        item_t3 = Item(meeting_id=m1.id, type=ItemType.action, text="Write settlement test plan", review_state=ReviewState.approved, evidence_quote="write settlement test plan")
        db.add(item_t3)
        db.flush()
        t3 = Task(item_id=item_t3.id, decision_id=d1.id, title="Write settlement test plan", owner_id=None, tracker_ref=None, status=TaskStatus.open, provisional=False, estimate_hours=10.0)
        db.add(t3)

        # T4 (with reminders)
        item_t4 = Item(meeting_id=m1.id, type=ItemType.action, text="Finance sign-off on vendor contract", review_state=ReviewState.approved, evidence_quote="finance sign-off on vendor contract")
        db.add(item_t4)
        db.flush()
        t4 = Task(item_id=item_t4.id, decision_id=d1.id, title="Finance sign-off on vendor contract", owner_id=karthik.id, tracker_ref=None, status=TaskStatus.open, provisional=False)
        db.add(t4)
        db.flush()

        rem1 = Reminder(task_id=t4.id, kind=ReminderKind.one_day, due_at=datetime.now(timezone.utc), state=ReminderState.pending)
        db.add(rem1)

        # Links
        lnk1 = Link(source_type="task", source_id=t1.id, target_type="decision", target_id=d1.id, relation=LinkRelation.implements, confirmed=True)
        lnk2 = Link(source_type="task", source_id=t2.id, target_type="decision", target_id=d1.id, relation=LinkRelation.implements, confirmed=True)
        lnk3 = Link(source_type="task", source_id=t3.id, target_type="decision", target_id=d1.id, relation=LinkRelation.implements, confirmed=True)
        lnk4 = Link(source_type="task", source_id=t4.id, target_type="decision", target_id=d1.id, relation=LinkRelation.implements, confirmed=True)
        db.add_all([lnk1, lnk2, lnk3, lnk4])

        # Pre-seed tracker tickets in tracker_tickets table
        ticket_t1 = TrackerTicket(ticket_ref=t1.tracker_ref, title=t1.title, assignee=ravi.tracker_id, labels=["decidr"])
        ticket_t2 = TrackerTicket(ticket_ref=t2.tracker_ref, title=t2.title, assignee=meera.tracker_id, labels=["decidr"])
        db.add_all([ticket_t1, ticket_t2])
        db.flush()

        # Meeting 2 with Sam's remark breaking P1
        m2 = Meeting(
            title="Meeting 2",
            date=date(2026, 11, 9),
            project="Payments Revamp",
            region="India",
            transcript_ref="m2.vtt",
            status=MeetingStatus.done,
        )
        db.add(m2)
        db.flush()

        utt = Utterance(
            meeting_id=m2.id,
            idx=15,
            speaker_raw="Sam",
            person_id=sam.id,
            text="Provider A told me this morning they only support T+2 settlement, not T+0 for merchant payouts",
        )
        db.add(utt)
        db.flush()

        alert = Alert(
            kind=AlertKind.premise_break,
            meeting_id=m2.id,
            utterance_id=utt.id,
            premise_id=p1.id,
            decision_id=d1.id,
            verdict="broken",
            old_quote="Provider A supports T+0 UPI settlement",
            new_quote="Provider A told me this morning they only support T+2 settlement, not T+0 for merchant payouts",
            explanation="Provider A only supports T+2 settlement for merchant payouts, breaking premise P1 upon which decision D1 depends.",
            state=AlertState.open,
        )
        db.add(alert)
        db.commit()

        return {
            "m1_id": m1.id,
            "m2_id": m2.id,
            "d1_id": d1.id,
            "p1_id": p1.id,
            "t1_id": t1.id,
            "t2_id": t2.id,
            "t3_id": t3.id,
            "t4_id": t4.id,
            "t1_ref": t1.tracker_ref,
            "t2_ref": t2.tracker_ref,
            "alert_id": alert.id,
            "uid": uid,
        }


def test_gold_repair_actions_generated_for_p1_break(client, p1_break_scenario):
    """
    Test 1: Gold repair actions are generated for the P1 break.
    - Premise break alert is confirmed.
    - Premise becomes status=broken and audit row written.
    - Blast radius is computed and repair plan (change_proposal in state draft) is generated.
    - Generated actions include:
      * mark_decision_at_risk for D1
      * comment_task for T1 (with broken premise, new quote, speaker 'Sam', date)
      * comment_task for T2 (with broken premise, new quote, speaker 'Sam', date)
      * pause_reminders for affected tasks
      * NO comment_task for T3/T4 (no tracker tickets)
      * Every action has idempotency_key = hash(alert_id, action_type, target_id)
    - Zero tracker writes made during draft generation (Invariant 2).
    """
    alert_id = p1_break_scenario["alert_id"]
    d1_id = p1_break_scenario["d1_id"]
    t1_id = p1_break_scenario["t1_id"]
    t2_id = p1_break_scenario["t2_id"]
    t3_id = p1_break_scenario["t3_id"]
    p1_id = p1_break_scenario["p1_id"]

    # 1. Reviewer confirms the break alert
    res = client.post(f"/review/alerts/{alert_id}/confirm", json={"actor": "reviewer_alice"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "confirmed"
    assert data["proposal_id"] is not None
    proposal_id = data["proposal_id"]

    # Verify premise status is broken
    with SessionLocal() as db:
        p1 = db.get(Premise, p1_id)
        assert p1.status == PremiseStatus.broken

    # 2. Fetch proposal via GET /proposals/{id}
    res_prop = client.get(f"/proposals/{proposal_id}")
    assert res_prop.status_code == 200
    prop_data = res_prop.json()
    assert prop_data["state"] == "draft"
    assert prop_data["trigger_type"] == "alert"
    assert prop_data["trigger_id"] == alert_id

    actions = prop_data["actions"]
    assert len(actions) >= 3

    # Check mark_decision_at_risk for D1
    d_actions = [a for a in actions if a["action_type"] == "mark_decision_at_risk" and a["target_id"] == d1_id]
    assert len(d_actions) == 1
    d_act = d_actions[0]
    assert d_act["target_type"] == "decision"
    assert d_act["state"] == "draft"
    expected_d_key = make_idempotency_key(alert_id, ActionType.mark_decision_at_risk, d1_id)
    assert d_act["idempotency_key"] == expected_d_key

    # Check comment_task for T1
    t1_comments = [a for a in actions if a["action_type"] == "comment_task" and a["target_id"] == t1_id]
    assert len(t1_comments) == 1
    t1_act = t1_comments[0]
    assert t1_act["target_type"] == "task"
    assert t1_act["state"] == "draft"
    expected_t1_key = make_idempotency_key(alert_id, ActionType.comment_task, t1_id)
    assert t1_act["idempotency_key"] == expected_t1_key
    comment_text_t1 = t1_act["payload"]["comment"]
    assert "Provider A supports T+0 UPI settlement" in comment_text_t1
    assert "T+2 settlement" in comment_text_t1
    assert "Sam" in comment_text_t1

    # Check comment_task for T2
    t2_comments = [a for a in actions if a["action_type"] == "comment_task" and a["target_id"] == t2_id]
    assert len(t2_comments) == 1
    t2_act = t2_comments[0]
    assert t2_act["idempotency_key"] == make_idempotency_key(alert_id, ActionType.comment_task, t2_id)

    # Check that T3 (no tracker ticket) has NO comment_task action
    t3_comments = [a for a in actions if a["action_type"] == "comment_task" and a["target_id"] == t3_id]
    assert len(t3_comments) == 0

    # Check pause_reminders exists for affected tasks
    pause_acts = [a for a in actions if a["action_type"] == "pause_reminders"]
    assert len(pause_acts) >= 1

    # Invariant 2 & 10 check: Zero comments in TrackerTicket table during proposal generation
    with SessionLocal() as db:
        t1_ticket = db.query(TrackerTicket).filter_by(ticket_ref=p1_break_scenario["t1_ref"]).first()
        assert t1_ticket is not None
        assert len(t1_ticket.comments or []) == 0


def test_reject_plan_zero_tracker_calls(client, p1_break_scenario):
    """
    Test 2: Rejecting a repair plan results in ZERO external tracker calls.
    """
    alert_id = p1_break_scenario["alert_id"]
    with SessionLocal() as db:
        proposal = generate_repair_plan(db, alert_id=alert_id, actor="reviewer_bob")
        db.commit()
        prop_id = proposal.id

    # Call POST /proposals/{id}/reject
    res_reject = client.post(f"/proposals/{prop_id}/reject", json={"actor": "reviewer_bob"})
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"

    # Verify database state
    with SessionLocal() as db:
        prop = db.get(ChangeProposal, prop_id)
        assert prop.state == ProposalState.rejected
        for act in prop.actions:
            assert act.state == ActionState.rejected

        # Verify zero comments on this scenario's tickets
        t1_ticket = db.query(TrackerTicket).filter_by(ticket_ref=p1_break_scenario["t1_ref"]).first()
        t2_ticket = db.query(TrackerTicket).filter_by(ticket_ref=p1_break_scenario["t2_ref"]).first()
        assert len(t1_ticket.comments or []) == 0
        assert len(t2_ticket.comments or []) == 0

    # Ensure executing a rejected proposal is rejected by executor
    with pytest.raises(ProposalNotApprovedError):
        execute_proposal(prop_id, actor="reviewer_bob")


def test_approve_twice_no_duplicate_comments(client, p1_break_scenario):
    """
    Test 3: Approving a proposal twice produces NO duplicate comments (Invariant 3).
    """
    alert_id = p1_break_scenario["alert_id"]
    t1_id = p1_break_scenario["t1_id"]

    with SessionLocal() as db:
        proposal = generate_repair_plan(db, alert_id=alert_id, actor="reviewer_alice")
        db.commit()
        prop_id = proposal.id
        t1_action = [a for a in proposal.actions if a.action_type == ActionType.comment_task and a.target_id == t1_id][0]
        t1_action_id = t1_action.id

    # First Approval
    res1 = client.post(
        f"/proposals/{prop_id}/approve",
        json={"actor": "reviewer_alice", "action_ids": [t1_action_id]},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["execution"]["executed_count"] == 1

    # Check ticket comments
    with SessionLocal() as db:
        t1_ticket = db.query(TrackerTicket).filter_by(ticket_ref=p1_break_scenario["t1_ref"]).first()
        comments_after_1st = t1_ticket.comments or []
        assert len(comments_after_1st) == 1
        first_comment_text = comments_after_1st[0]["text"]

    # Second Approval (exact same action)
    res2 = client.post(
        f"/proposals/{prop_id}/approve",
        json={"actor": "reviewer_alice", "action_ids": [t1_action_id]},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["execution"]["executed_count"] == 0
    assert data2["execution"]["skipped_count"] >= 1

    # Verify STILL exactly 1 comment in tracker
    with SessionLocal() as db:
        t1_ticket = db.query(TrackerTicket).filter_by(ticket_ref=p1_break_scenario["t1_ref"]).first()
        comments_after_2nd = t1_ticket.comments or []
        assert len(comments_after_2nd) == 1
        assert comments_after_2nd[0]["text"] == first_comment_text


def test_partial_approval_executes_only_selected_actions(client, p1_break_scenario):
    """
    Test 4: Partial approval executes ONLY the selected actions.
    Non-selected actions remain unexecuted/rejected with zero tracker writes.
    """
    alert_id = p1_break_scenario["alert_id"]
    t1_id = p1_break_scenario["t1_id"]
    t2_id = p1_break_scenario["t2_id"]
    d1_id = p1_break_scenario["d1_id"]

    with SessionLocal() as db:
        proposal = generate_repair_plan(db, alert_id=alert_id, actor="reviewer_alice")
        db.commit()
        prop_id = proposal.id
        t1_action = [a for a in proposal.actions if a.action_type == ActionType.comment_task and a.target_id == t1_id][0]
        t2_action = [a for a in proposal.actions if a.action_type == ActionType.comment_task and a.target_id == t2_id][0]
        d1_action = [a for a in proposal.actions if a.action_type == ActionType.mark_decision_at_risk and a.target_id == d1_id][0]

        t1_act_id = t1_action.id
        t2_act_id = t2_action.id
        d1_act_id = d1_action.id

    # Approve ONLY T1 comment and D1 mark_at_risk, explicitly excluding T2
    res = client.post(
        f"/proposals/{prop_id}/approve",
        json={"actor": "reviewer_alice", "action_ids": [t1_act_id, d1_act_id]},
    )
    assert res.status_code == 200

    with SessionLocal() as db:
        # Check D1 status was updated to at_risk
        d1 = db.get(Decision, d1_id)
        assert d1.status == DecisionStatus.at_risk

        # Check T1 ticket got a comment
        t1_ticket = db.query(TrackerTicket).filter_by(ticket_ref=p1_break_scenario["t1_ref"]).first()
        assert len(t1_ticket.comments or []) == 1

        # Check T2 ticket has ZERO comments
        t2_ticket = db.query(TrackerTicket).filter_by(ticket_ref=p1_break_scenario["t2_ref"]).first()
        assert len(t2_ticket.comments or []) == 0

        # Check action states in db
        a1 = db.get(ChangeAction, t1_act_id)
        a2 = db.get(ChangeAction, t2_act_id)
        ad = db.get(ChangeAction, d1_act_id)
        assert a1.state == ActionState.executed
        assert ad.state == ActionState.executed
        assert a2.state == ActionState.rejected


def test_preview_payload_equals_executed_payload(client, p1_break_scenario):
    """
    Test 5: The payload shown in the preview equals the exact payload executed.
    """
    alert_id = p1_break_scenario["alert_id"]
    t1_id = p1_break_scenario["t1_id"]

    with SessionLocal() as db:
        proposal = generate_repair_plan(db, alert_id=alert_id, actor="reviewer_alice")
        db.commit()
        prop_id = proposal.id
        t1_action = [a for a in proposal.actions if a.action_type == ActionType.comment_task and a.target_id == t1_id][0]
        t1_act_id = t1_action.id

    # 1. Fetch dry-run preview via GET /proposals/{id}/preview
    res_preview = client.get(f"/proposals/{prop_id}/preview")
    assert res_preview.status_code == 200
    preview_data = res_preview.json()
    assert preview_data["dry_run"] is True

    preview_t1 = [p for p in preview_data["planned_actions"] if p["action_id"] == t1_act_id][0]
    expected_ref = preview_t1["payload"]["ref"]
    expected_text = preview_t1["payload"]["text"]

    # 2. Approve and execute
    res_approve = client.post(
        f"/proposals/{prop_id}/approve",
        json={"actor": "reviewer_alice", "action_ids": [t1_act_id]},
    )
    assert res_approve.status_code == 200

    # 3. Check actual comment in MockTracker
    with SessionLocal() as db:
        t1_ticket = db.query(TrackerTicket).filter_by(ticket_ref=expected_ref).first()
        comments = t1_ticket.comments or []
        assert len(comments) == 1
        executed_comment = comments[0]

        # Exact match between preview payload and executed action
        assert executed_comment["text"] == expected_text

        # Verify action result in db
        act = db.get(ChangeAction, t1_act_id)
        assert act.result["ref"] == expected_ref
        assert act.result["comment"] == expected_text


def test_reopen_task_for_done_tasks(client, p1_break_scenario):
    """
    Test 6: Rule for reopen_task: affected tasks marked 'done' generate a reopen_task action.
    """
    alert_id = p1_break_scenario["alert_id"]
    t2_id = p1_break_scenario["t2_id"]

    # Mark T2 as done before generating repair plan
    with SessionLocal() as db:
        t2 = db.get(Task, t2_id)
        t2.status = TaskStatus.done
        db.commit()

    with SessionLocal() as db:
        proposal = generate_repair_plan(db, alert_id=alert_id, actor="reviewer_alice")
        db.commit()
        prop_id = proposal.id

        reopen_acts = [a for a in proposal.actions if a.action_type == ActionType.reopen_task and a.target_id == t2_id]
        assert len(reopen_acts) == 1
        reopen_act = reopen_acts[0]
        assert reopen_act.idempotency_key == make_idempotency_key(alert_id, ActionType.reopen_task, t2_id)
        reopen_act_id = reopen_act.id

    # Approve reopen action
    res = client.post(
        f"/proposals/{prop_id}/approve",
        json={"actor": "reviewer_alice", "action_ids": [reopen_act_id]},
    )
    assert res.status_code == 200

    # Verify T2 is now open
    with SessionLocal() as db:
        t2 = db.get(Task, t2_id)
        assert t2.status == TaskStatus.open
