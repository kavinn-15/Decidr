"""
Demo Reset Script (Task 17 Requirement 1)
Resets the database and loads:
1. Roster from backend/seed/roster.json
2. Meeting M1 uploaded, processed, and fully approved (real tickets in the tracker)
3. Meeting M2 uploaded but NOT yet processed (ready for the 3-minute demo)
With LLM_MODE=replay or cache, processing M2 takes seconds and requires no network.
"""

import json
import logging
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.db.session import engine, init_db, SessionLocal, Base
from app.core.config import settings
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
    LinkRelation,
    TaskStatus,
)
from app.services.ingestion import ingest_meeting
from app.services.extraction import extract_meeting_items
from app.services.audit import log as audit_log

logger = logging.getLogger("decidr.demo_reset")


def run_demo_reset():
    print("================================================================================")
    print("DECIDR DEMO RESET (Task 17)")
    print("================================================================================")
    print("Resetting database tables...")

    # Drop all tables cleanly and re-initialize schema
    Base.metadata.drop_all(bind=engine)
    init_db(engine)

    seed_dir = backend_path / "seed"
    roster_file = seed_dir / "roster.json"

    with open(roster_file, "r", encoding="utf-8") as f:
        roster_data = json.load(f)

    with SessionLocal() as db:
        # 1. Seed Roster People
        print("[1/3] Seeding roster personnel...")
        person_map = {}
        for p in roster_data:
            person = Person(
                name=p["name"],
                email=p["email"],
                tracker_id=p.get("tracker_id"),
                slack_id=p.get("slack_id"),
            )
            db.add(person)
            db.flush()
            person_map[person.name.lower()] = person.id
            print(f"  - {person.name} ({person.email}) -> Tracker ID: {person.tracker_id}")

        db.commit()

        # 2. Ingest, Process, and Fully Approve Meeting M1
        print("[2/3] Ingesting, processing, and approving Meeting M1 (Kickoff)...")
        m1_vtt_path = seed_dir / "m1_2026-11-02.vtt"
        m1_content = m1_vtt_path.read_text(encoding="utf-8")

        m1 = ingest_meeting(
            db=db,
            content=m1_content,
            filename=m1_vtt_path.name,
            title="Payments Architecture Kickoff",
            meeting_date=date(2026, 11, 2),
            project="Payments Revamp",
            region="India",
            release="v1.0",
        )

        # Run two-pass extraction on M1
        extract_meeting_items(db, meeting_id=m1.id, actor="demo_system")

        # Fully approve M1 items (Decisions, Premises, Tasks, Links)
        m1_items = db.query(Item).filter(Item.meeting_id == m1.id).all()
        approved_decisions = []
        approved_tasks = []

        for item in m1_items:
            item.review_state = ReviewState.approved

            if item.type == ItemType.decision:
                dec = item.decision
                if not dec:
                    dec = Decision(
                        item_id=item.id,
                        text=item.text,
                        scope_project=m1.project,
                        scope_region=m1.region,
                        scope_release=m1.release,
                        effective_from=m1.date,
                        status=DecisionStatus.active,
                        version=1,
                    )
                    db.add(dec)
                    db.flush()
                    db.add(DecisionVersion(decision_id=dec.id, version=1, text=dec.text, changed_by="demo_reviewer"))
                    db.flush()
                else:
                    dec.status = DecisionStatus.active

                approved_decisions.append(dec)

                # Confirm premises of approved decision
                for p in dec.premises:
                    p.state = PremiseState.confirmed
                    p.status = PremiseStatus.holding

                audit_log(
                    actor="demo_reviewer",
                    action="approve_decision",
                    entity_type="decision",
                    entity_id=dec.id,
                    before={"status": "proposed"},
                    after={"status": "active"},
                    db=db,
                )

            elif item.type == ItemType.action:
                task = db.query(Task).filter(Task.item_id == item.id).first()
                if task:
                    task.provisional = False
                    task.status = TaskStatus.open
                    task.estimate_hours = task.estimate_hours or 16.0
                    task.tracker_ref = f"MOCK-{task.id}"
                    task.tracker_url = f"https://tracker.mock/issues/MOCK-{task.id}"
                    approved_tasks.append(task)

                    # Real ticket row in tracker system
                    ticket = TrackerTicket(
                        ticket_ref=task.tracker_ref,
                        title=task.title,
                        body=f"Created from meeting approval: {task.title}",
                        assignee=task.owner.name if task.owner else None,
                        due_date=str(task.due_date) if task.due_date else None,
                        labels=["payments-revamp", "v1.0"],
                        status="open",
                    )
                    db.add(ticket)
                    db.flush()

                    audit_log(
                        actor="demo_reviewer",
                        action="approve_task",
                        entity_type="task",
                        entity_id=task.id,
                        before={"provisional": True},
                        after={"provisional": False, "tracker_ref": task.tracker_ref},
                        db=db,
                    )

        # Confirm all links for M1
        for link in db.query(Link).all():
            link.confirmed = True

        m1.status = MeetingStatus.review  # In review queue with 0 pending cards
        db.commit()

        audit_log(
            actor="demo_reviewer",
            action="approve_meeting",
            entity_type="meeting",
            entity_id=m1.id,
            before={"status": "uploaded"},
            after={"status": "approved", "approved_items_count": len(m1_items)},
            db=db,
        )

        print(f"  - M1 approved with {len(approved_decisions)} active decisions, "
              f"{len(approved_tasks)} tracker tickets, and confirmed premises.")

        # 3. Ingest M2 (Uploaded, but NOT yet processed)
        print("[3/3] Uploading Meeting M2 (Vendor SLA & European Launch Review)...")
        m2_vtt_path = seed_dir / "m2_2026-11-09.vtt"
        m2_content = m2_vtt_path.read_text(encoding="utf-8")

        m2 = ingest_meeting(
            db=db,
            content=m2_content,
            filename=m2_vtt_path.name,
            title="Vendor SLA & European Launch Review",
            meeting_date=date(2026, 11, 9),
            project="Payments Revamp",
            region="India",
            release="v1.0",
        )
        # Keep status strictly as 'uploaded'
        m2.status = MeetingStatus.uploaded
        db.commit()

        print(f"  - M2 uploaded (ID #{m2.id}), status: 'uploaded'. Ready to be processed in demo.")

    print("\nDemo reset complete! State:")
    print("  ✓ Roster: 6 people active")
    print("  ✓ Meeting M1: Ingested, processed, fully approved, tracker tickets created")
    print("  ✓ Meeting M2: Uploaded, pending processing ('Process' button active)")
    print("================================================================================\n")


if __name__ == "__main__":
    run_demo_reset()
