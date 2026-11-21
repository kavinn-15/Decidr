import io
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm.adapter import adapter
from app.models.enums import ItemType, ReviewState, MeetingStatus, TaskStatus, LinkRelation
from app.models.models import Person, Meeting, Utterance, Item, Decision, Premise, Task, Link
from app.services.ingestion import ingest_meeting
from app.services.extraction import (
    resolve_relative_date,
    extract_meeting_items,
    Pass1Output,
    DecisionExtracted,
    ActionExtracted,
    Pass2Output,
    PremiseExtracted,
)


def test_relative_dates_resolve():
    """
    Invariant 8: Relative dates are resolved against the meeting date and stored as ISO dates.
    """
    meeting_date = date(2026, 11, 2)

    d1 = resolve_relative_date("by Nov 20", meeting_date)
    assert d1 == date(2026, 11, 20)

    d2 = resolve_relative_date("Nov 12", meeting_date)
    assert d2 == date(2026, 11, 12)

    d3 = resolve_relative_date("until Nov 30", date(2026, 11, 23))
    assert d3 == date(2026, 11, 30)

    # Empty / none phrases return None
    assert resolve_relative_date(None, meeting_date) is None
    assert resolve_relative_date("", meeting_date) is None


def test_quote_verification_drops_fabricated_quote(db):
    """
    Invariant 6: Every evidence_quote must be an exact substring of the transcript;
    if it is not, discard the item and log it.
    """
    person = Person(name="Asha", email="asha.test@decidr.local", tracker_id="ASHA-1")
    db.add(person)
    db.commit()

    transcript = """WEBVTT

00:00:01.000 --> 00:00:04.000
Asha: We have decided to use Provider A for India settlements.
"""
    meeting = ingest_meeting(
        db=db,
        content=transcript,
        filename="test_quotes.vtt",
        title="Quote Verification Meeting",
        meeting_date=date(2026, 11, 2),
        project="Payments Revamp",
    )

    # Configure fake LLM responses with a fabricated quote
    original_provider = settings.LLM_PROVIDER
    original_mode = settings.LLM_MODE
    settings.LLM_PROVIDER = "fake"
    settings.LLM_MODE = "live"

    try:
        # Enqueue Pass 1 response with a fabricated quote not in the transcript
        fake_pass1 = Pass1Output(
            decisions=[
                DecisionExtracted(
                    text="Use Provider Z for global payments",
                    evidence_quote="we decided to use Provider Z globally next year",  # FABRICATED!
                    utterance_idx=0,
                    confidence=0.9,
                )
            ],
            actions=[
                ActionExtracted(
                    text="Integrate Provider Z",
                    owner_name="Asha",
                    deadline_phrase="by next week",
                    evidence_quote="Asha will integrate Provider Z next week",  # FABRICATED!
                    utterance_idx=0,
                    confidence=0.9,
                )
            ],
        )
        adapter.enqueue_fake_response(fake_pass1)

        result = extract_meeting_items(db, meeting.id)

        # Both fabricated items must be dropped
        assert result["dropped_quotes"] == 2
        assert result["decisions_count"] == 0
        assert result["actions_count"] == 0

        # Assert nothing was saved in DB
        items = db.query(Item).filter_by(meeting_id=meeting.id).all()
        assert len(items) == 0

    finally:
        settings.LLM_PROVIDER = original_provider
        settings.LLM_MODE = original_mode


def test_missing_owner_and_deadline_flagged_never_guessed(db):
    """
    Invariant 1: Never guess an owner or deadline. If missing, store null and flag
    the item 'needs owner' or 'needs deadline'.
    """
    meera = Person(name="Meera", email="meera.test@decidr.local", tracker_id="MEERA-1")
    db.add(meera)
    db.commit()

    transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
Asha: We will use Provider A for India settlements.

00:00:05.500 --> 00:00:10.000
Meera: I will build settlement reconciliation screen for merchant ops.

00:00:10.500 --> 00:00:15.000
Divya: Someone needs to write settlement test plan by Nov 25.
"""
    meeting = ingest_meeting(
        db=db,
        content=transcript,
        filename="test_invariants.vtt",
        title="Invariants Test Meeting",
        meeting_date=date(2026, 11, 2),
        project="Payments Revamp",
    )

    original_provider = settings.LLM_PROVIDER
    original_mode = settings.LLM_MODE
    settings.LLM_PROVIDER = "fake"
    settings.LLM_MODE = "live"

    try:
        # Pass 1: Extract 1 decision, 2 actions
        fake_pass1 = Pass1Output(
            decisions=[
                DecisionExtracted(
                    text="Use Provider A for India settlements",
                    evidence_quote="We will use Provider A for India settlements.",
                    utterance_idx=0,
                    confidence=0.95,
                    region_mentioned="India",
                )
            ],
            actions=[
                # Action 1: Owner Meera, NO deadline phrase
                ActionExtracted(
                    text="Build settlement reconciliation screen",
                    owner_name="Meera",
                    deadline_phrase=None,
                    evidence_quote="I will build settlement reconciliation screen for merchant ops.",
                    utterance_idx=1,
                    confidence=0.9,
                    related_decision_hint="Provider A",
                ),
                # Action 2: NO owner, deadline "Nov 25"
                ActionExtracted(
                    text="Write settlement test plan",
                    owner_name=None,
                    deadline_phrase="Nov 25",
                    evidence_quote="Someone needs to write settlement test plan by Nov 25.",
                    utterance_idx=2,
                    confidence=0.9,
                    related_decision_hint="Provider A",
                ),
            ],
        )
        adapter.enqueue_fake_response(fake_pass1)

        # Pass 2: Premise for decision
        fake_pass2 = Pass2Output(
            premises=[
                PremiseExtracted(
                    text="Provider A is selected for India settlements",
                    evidence_quote="We will use Provider A for India settlements.",
                    utterance_idx=0,
                )
            ]
        )
        adapter.enqueue_fake_response(fake_pass2)

        result = extract_meeting_items(db, meeting.id)
        assert result["decisions_count"] == 1
        assert result["actions_count"] == 2
        assert result["dropped_quotes"] == 0

        # Query actions and verify Invariant 1
        tasks = db.query(Task).join(Item, Task.item_id == Item.id).filter(Item.meeting_id == meeting.id).all()
        assert len(tasks) == 2

        # Task 1: Has owner Meera, missing deadline
        task1 = [t for t in tasks if "reconciliation" in t.title.lower()][0]
        assert task1.owner_id == meera.id
        assert task1.item.needs_owner is False
        assert task1.due_date is None
        assert task1.item.needs_deadline is True

        # Task 2: Missing owner, has deadline Nov 25
        task2 = [t for t in tasks if "test plan" in t.title.lower()][0]
        assert task2.owner_id is None
        assert task2.item.needs_owner is True
        assert task2.due_date == date(2026, 11, 25)
        assert task2.item.needs_deadline is False

        # Verify all items have review_state = proposed
        items = db.query(Item).filter_by(meeting_id=meeting.id).all()
        assert all(it.review_state == ReviewState.proposed for it in items)

        # Verify links
        links = db.query(Link).all()
        assert len(links) >= 2
        assert all(l.relation == LinkRelation.implements for l in links)

    finally:
        settings.LLM_PROVIDER = original_provider
        settings.LLM_MODE = original_mode


def test_post_process_meeting_endpoint(client: TestClient, db):
    """
    Test POST /meetings/{id}/process background task triggering and status update.
    """
    person = Person(name="Asha", email="asha.process@decidr.local", tracker_id="ASHA-PROC")
    db.add(person)
    db.commit()

    transcript_content = b"""WEBVTT

00:00:01.000 --> 00:00:04.000
Asha: We will use Provider A for India settlements.
"""
    # Create meeting via API
    res_post = client.post(
        "/meetings",
        data={"title": "Processing Test", "date": "2026-11-02", "project": "Payments Revamp"},
        files={"file": ("test.vtt", io.BytesIO(transcript_content), "text/vtt")},
    )
    assert res_post.status_code == 201
    meeting_id = res_post.json()["id"]

    original_provider = settings.LLM_PROVIDER
    settings.LLM_PROVIDER = "fake"

    try:
        fake_pass1 = Pass1Output(
            decisions=[
                DecisionExtracted(
                    text="Use Provider A for India settlements",
                    evidence_quote="We will use Provider A for India settlements.",
                    utterance_idx=0,
                )
            ],
            actions=[],
        )
        fake_pass2 = Pass2Output(premises=[])
        adapter.enqueue_fake_response(fake_pass1)
        adapter.enqueue_fake_response(fake_pass2)

        # Trigger process endpoint
        res_proc = client.post(f"/meetings/{meeting_id}/process")
        assert res_proc.status_code == 200
        assert res_proc.json()["status"] == "processing"

        # Check meeting status updated to review
        res_get = client.get(f"/meetings/{meeting_id}")
        assert res_get.status_code == 200
        assert res_get.json()["status"] == MeetingStatus.review.value

    finally:
        settings.LLM_PROVIDER = original_provider
