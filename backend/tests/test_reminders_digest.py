import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal, init_db, engine
from app.models.models import (
    Person,
    Meeting,
    Item,
    Decision,
    Premise,
    Task,
    Link,
    Reminder,
    Outbox,
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
    ReminderKind,
    ReminderState,
    ReminderChannel,
)
from app.services.reminders import (
    create_task_reminders,
    run_reminders,
    check_task_premise_shaky,
)
from app.services.digest import (
    build_digest,
    generate_and_schedule_weekly_digests,
)


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.TRACKER = "mock"
    settings.LLM_PROVIDER = "fake"
    settings.LLM_MODE = "live"
    settings.TIMEZONE = "UTC"
    init_db(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_scenario():
    """
    Sets up a test team with Ravi and Meera, a meeting, decision D1, premise P1, and tasks.
    """
    with SessionLocal() as db:
        uid = uuid.uuid4().hex[:6]

        ravi = Person(name="Ravi", email=f"ravi_{uid}@example.com", tracker_id=f"ravi_{uid}")
        meera = Person(name="Meera", email=f"meera_{uid}@example.com", tracker_id=f"meera_{uid}")
        db.add_all([ravi, meera])
        db.flush()

        m1 = Meeting(
            title="Payments Architecture",
            date=date(2026, 11, 2),
            project="Payments Revamp",
            region="India",
            transcript_ref="m1.vtt",
            status=MeetingStatus.done,
        )
        db.add(m1)
        db.flush()

        # Decision D1
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

        # Ravi's task T1 (due Nov 20, 2026)
        item_t1 = Item(
            meeting_id=m1.id,
            type=ItemType.action,
            text="Integrate Provider A SDK",
            review_state=ReviewState.approved,
            evidence_quote="integrate Provider A SDK",
        )
        db.add(item_t1)
        db.flush()

        t1 = Task(
            item_id=item_t1.id,
            decision_id=d1.id,
            title="Integrate Provider A SDK",
            owner_id=ravi.id,
            due_date=date(2026, 11, 20),
            tracker_ref=f"MOCK-T1-{uid}",
            tracker_url=f"http://mock/t1-{uid}",
            status=TaskStatus.open,
            provisional=False,
            estimate_hours=20.0,
        )
        db.add(t1)

        # Meera's task T2 (due Nov 21, 2026)
        item_t2 = Item(
            meeting_id=m1.id,
            type=ItemType.action,
            text="Build reconciliation screen",
            review_state=ReviewState.approved,
            evidence_quote="build reconciliation screen",
        )
        db.add(item_t2)
        db.flush()

        t2 = Task(
            item_id=item_t2.id,
            decision_id=d1.id,
            title="Build reconciliation screen",
            owner_id=meera.id,
            due_date=date(2026, 11, 21),
            tracker_ref=f"MOCK-T2-{uid}",
            tracker_url=f"http://mock/t2-{uid}",
            status=TaskStatus.open,
            provisional=False,
            estimate_hours=15.0,
        )
        db.add(t2)
        db.flush()

        # Confirmed links
        lnk1 = Link(
            source_type="task",
            source_id=t1.id,
            target_type="decision",
            target_id=d1.id,
            relation=LinkRelation.implements,
            confirmed=True,
        )
        lnk2 = Link(
            source_type="task",
            source_id=t2.id,
            target_type="decision",
            target_id=d1.id,
            relation=LinkRelation.implements,
            confirmed=True,
        )
        db.add_all([lnk1, lnk2])
        db.commit()

        return {
            "ravi_id": ravi.id,
            "meera_id": meera.id,
            "d1_id": d1.id,
            "p1_id": p1.id,
            "t1_id": t1.id,
            "t2_id": t2.id,
        }


def test_three_reminders_created_per_dated_task(test_scenario):
    """
    Test 1: When a task with a due date is created, 3 reminders are created
    (3 days before, 1 day before, and morning-of at 08:00 local time).
    """
    with SessionLocal() as db:
        task = db.get(Task, test_scenario["t1_id"])
        assert task.due_date == date(2026, 11, 20)

        reminders = create_task_reminders(db, task, timezone_str="UTC")
        assert len(reminders) == 3

        kinds = {r.kind for r in reminders}
        assert kinds == {ReminderKind.three_day, ReminderKind.one_day, ReminderKind.morning}

        for r in reminders:
            assert r.state == ReminderState.pending
            assert r.task_id == task.id

            # Verify due_at hours
            assert r.due_at.hour == 8
            assert r.due_at.minute == 0
            if r.kind == ReminderKind.three_day:
                assert r.due_at.date() == date(2026, 11, 17)
            elif r.kind == ReminderKind.one_day:
                assert r.due_at.date() == date(2026, 11, 19)
            elif r.kind == ReminderKind.morning:
                assert r.due_at.date() == date(2026, 11, 20)


def test_running_twice_sends_once(test_scenario):
    """
    Test 2: Running reminders twice sends each reminder at most once (0 duplicate emails/outbox records).
    """
    with SessionLocal() as db:
        # Cancel any pending reminders from other fixtures to have an isolated count
        db.query(Reminder).filter(Reminder.state == ReminderState.pending).update({Reminder.state: ReminderState.cancelled})
        db.commit()

        task = db.get(Task, test_scenario["t1_id"])
        create_task_reminders(db, task, timezone_str="UTC")
        db.commit()

        initial_outbox_count = db.query(Outbox).count()

        # Run 1: Simulated time is 2026-11-20 09:00 UTC (past all 3 reminders)
        res1 = run_reminders(db, now=datetime(2026, 11, 20, 9, 0, 0, tzinfo=timezone.utc))
        assert res1["sent_count"] == 3
        assert res1["failed_count"] == 0

        # Verify reminders state is sent
        reminders = db.query(Reminder).filter(Reminder.task_id == task.id).all()
        for r in reminders:
            assert r.state == ReminderState.sent

        # Verify outbox has 3 new messages
        new_outbox_count = db.query(Outbox).count()
        assert new_outbox_count == initial_outbox_count + 3

        # Run 2: Simulated time is 2026-11-20 10:00 UTC
        res2 = run_reminders(db, now=datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc))
        assert res2["sent_count"] == 0

        # Outbox count remains unchanged (0 duplicate sends)
        final_outbox_count = db.query(Outbox).count()
        assert final_outbox_count == new_outbox_count


def test_paused_reminders_are_skipped(test_scenario):
    """
    Test 3: Paused reminders are never sent.
    """
    with SessionLocal() as db:
        task = db.get(Task, test_scenario["t1_id"])
        reminders = create_task_reminders(db, task, timezone_str="UTC")

        # Pause one of the reminders
        morning_rem = next(r for r in reminders if r.kind == ReminderKind.morning)
        morning_rem.state = ReminderState.paused
        morning_rem.pause_reason = "Premise broken"
        db.commit()

        # Run at 2026-11-20 09:00 UTC
        res = run_reminders(db, now=datetime(2026, 11, 20, 9, 0, 0, tzinfo=timezone.utc))

        # Only 2 reminders should have been sent (3d and 1d)
        assert res["sent_count"] == 2

        db.refresh(morning_rem)
        assert morning_rem.state == ReminderState.paused
        assert morning_rem.pause_reason == "Premise broken"

        # Outbox does not have morning reminder
        morning_outbox = (
            db.query(Outbox)
            .filter(Outbox.subject.contains("Morning-of Reminder"))
            .all()
        )
        assert len(morning_outbox) == 0


def test_digest_for_ravi_includes_tasks_resting_on_broken_premise(test_scenario):
    """
    Test 4: Digest for Ravi includes tasks resting on broken premise P1 in the
    'Work resting on broken or shaky premises' section.
    """
    with SessionLocal() as db:
        # Break premise P1
        p1 = db.get(Premise, test_scenario["p1_id"])
        p1.status = PremiseStatus.broken
        db.commit()

        digest = build_digest(person_id=test_scenario["ravi_id"], as_of=date(2026, 11, 15), db=db)

        # Check section in JSON
        broken_section = digest["sections"]["work_resting_on_broken_or_shaky_premises"]
        assert len(broken_section) >= 1

        t1_item = next((item for item in broken_section if item["task_id"] == test_scenario["t1_id"]), None)
        assert t1_item is not None
        assert t1_item["task_title"] == "Integrate Provider A SDK"
        assert t1_item["premise_id"] == p1.id
        assert t1_item["premise_status"] == "broken"
        assert "BROKEN" in t1_item["reason"]

        # Check plain text output contains section
        text = digest["rendered_text"]
        assert "5. WORK RESTING ON BROKEN OR SHAKY PREMISES" in text
        assert "Integrate Provider A SDK" in text
        assert "BROKEN" in text

        # Check HTML output contains section
        html = digest["rendered_html"]
        assert "Work Resting on Broken or Shaky Premises" in html
        assert "Integrate Provider A SDK" in html
        assert "BROKEN" in html


def test_digest_never_lists_a_task_under_someone_elses_name(test_scenario):
    """
    Test 5: Personal isolation invariant — Digest NEVER lists tasks owned by anyone else.
    Ravi's digest never lists Meera's task (T2), and Meera's digest never lists Ravi's task (T1).
    """
    with SessionLocal() as db:
        ravi_digest = build_digest(person_id=test_scenario["ravi_id"], as_of=date(2026, 11, 15), db=db)
        meera_digest = build_digest(person_id=test_scenario["meera_id"], as_of=date(2026, 11, 15), db=db)

        ravi_id = test_scenario["ravi_id"]
        meera_id = test_scenario["meera_id"]

        # In Ravi's digest:
        # due_this_week
        for t in ravi_digest["sections"]["due_this_week"]:
            assert t["owner_id"] == ravi_id
            assert t["id"] != test_scenario["t2_id"]

        # overdue
        for t in ravi_digest["sections"]["overdue"]:
            assert t["owner_id"] == ravi_id
            assert t["id"] != test_scenario["t2_id"]

        # work_resting_on_broken_or_shaky_premises
        for t in ravi_digest["sections"]["work_resting_on_broken_or_shaky_premises"]:
            assert t["owner_id"] == ravi_id
            assert t["task_id"] != test_scenario["t2_id"]

        # In Meera's digest:
        for t in meera_digest["sections"]["due_this_week"]:
            assert t["owner_id"] == meera_id
            assert t["id"] != test_scenario["t1_id"]

        for t in meera_digest["sections"]["overdue"]:
            assert t["owner_id"] == meera_id
            assert t["id"] != test_scenario["t1_id"]

        for t in meera_digest["sections"]["work_resting_on_broken_or_shaky_premises"]:
            assert t["owner_id"] == meera_id
            assert t["task_id"] != test_scenario["t1_id"]


def test_shaky_premise_adds_warning_to_reminder_text(test_scenario):
    """
    Test 6: If a task's premise is shaky (possible break not yet confirmed),
    the reminder text adds "The reason for this task may no longer hold; please review".
    """
    with SessionLocal() as db:
        # Set premise P1 to shaky
        p1 = db.get(Premise, test_scenario["p1_id"])
        p1.status = PremiseStatus.shaky
        db.commit()

        task = db.get(Task, test_scenario["t1_id"])
        assert check_task_premise_shaky(db, task) is True

        create_task_reminders(db, task, timezone_str="UTC")
        db.commit()

        # Run reminder at 2026-11-17 09:00 UTC (triggers 3-day reminder)
        res = run_reminders(db, now=datetime(2026, 11, 17, 9, 0, 0, tzinfo=timezone.utc))
        assert res["sent_count"] == 1

        # Check outbox body
        outbox_entry = (
            db.query(Outbox)
            .filter(Outbox.to_addr == "ravi_" + task.tracker_ref.split("-")[-1] + "@example.com")
            .order_by(Outbox.id.desc())
            .first()
        )
        assert outbox_entry is not None
        assert "The reason for this task may no longer hold; please review" in outbox_entry.body


def test_reminders_digest_api_endpoints(client, test_scenario):
    """
    Test 7: Verify API routes for /digest/{id}, /admin/run-reminders, /admin/run-digest,
    /my-week/{id}, and /outbox.
    """
    ravi_id = test_scenario["ravi_id"]

    # 1. GET /digest/{person_id}
    resp = client.get(f"/digest/{ravi_id}?as_of=2026-11-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["person_id"] == ravi_id
    assert "sections" in data
    assert "rendered_text" in data
    assert "rendered_html" in data

    # 2. POST /admin/run-reminders
    resp_rem = client.post("/admin/run-reminders?now=2026-11-20T09:00:00Z")
    assert resp_rem.status_code == 200
    rem_data = resp_rem.json()
    assert "sent_count" in rem_data

    # 3. POST /admin/run-digest
    resp_dig = client.post("/admin/run-digest?as_of=2026-11-15")
    assert resp_dig.status_code == 200
    dig_data = resp_dig.json()
    assert dig_data["status"] == "scheduled"
    assert dig_data["digests_created"] >= 2

    # 4. GET /my-week/{person_id}
    resp_week = client.get(f"/my-week/{ravi_id}?as_of=2026-11-15")
    assert resp_week.status_code == 200
    week_data = resp_week.json()
    assert week_data["person_id"] == ravi_id
    assert "week_schedule" in week_data
    assert "broken_shaky_work" in week_data

    # 5. GET /outbox
    resp_out = client.get("/outbox?limit=10")
    assert resp_out.status_code == 200
    out_items = resp_out.json()
    assert isinstance(out_items, list)
    assert len(out_items) > 0
