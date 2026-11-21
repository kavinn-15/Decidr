from datetime import date, datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.models import AuditLog, Meeting, Utterance, Item, Alert
from app.models.enums import MeetingStatus, ItemType, ReviewState, AlertKind, AlertState
from app.services.audit import log


def test_audit_list_endpoint_returns_newest_first(client, db: Session):
    # Create distinct audit logs
    log(actor="Asha", action="test_action_1", entity_type="item", entity_id=1, before=None, after={"v": 1}, db=db)
    log(actor="Ravi", action="test_action_2", entity_type="task", entity_id=2, before={"v": 1}, after={"v": 2}, db=db)
    db.commit()

    resp = client.get("/audit?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    items = data["items"]
    assert len(items) >= 2
    # Ensure newest-first (descending IDs)
    assert items[0]["id"] > items[1]["id"]


def test_audit_filtering_by_actor_and_action(client, db: Session):
    log(actor="FilterActorA", action="action_unique_a", entity_type="meeting", entity_id=10, db=db)
    log(actor="FilterActorB", action="action_unique_b", entity_type="meeting", entity_id=11, db=db)
    db.commit()

    # Filter by actor
    resp = client.get("/audit?actor=FilterActorA")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["actor"] == "FilterActorA" for item in data["items"])
    assert any(item["action"] == "action_unique_a" for item in data["items"])

    # Filter by action
    resp2 = client.get("/audit?action=action_unique_b")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert all(item["action"] == "action_unique_b" for item in data2["items"])


def test_audit_csv_export(client, db: Session):
    log(actor="CsvActor", action="csv_export_action", entity_type="decision", entity_id=99, before={"old": "val"}, after={"new": "val"}, db=db)
    db.commit()

    resp = client.get("/audit/export?actor=CsvActor")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment; filename=" in resp.headers["content-disposition"]
    text = resp.text
    assert "ID,Timestamp (UTC),Actor,Action,Entity Type,Entity ID,Before,After" in text
    assert "CsvActor" in text
    assert "csv_export_action" in text


def test_meetings_dashboard_includes_pending_review_count(client, db: Session):
    meeting = Meeting(
        title="Dashboard Test Sync",
        date=date(2026, 11, 21),
        project="Payments Revamp",
        transcript_ref="seed/test.vtt",
        status=MeetingStatus.review,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # 1 proposed decision
    dec_item = Item(
        meeting_id=meeting.id,
        type=ItemType.decision,
        text="Dashboard Decision",
        evidence_quote="Dashboard Decision Quote",
        review_state=ReviewState.proposed,
        confidence=1.0,
    )
    # 1 open alert
    alert = Alert(
        meeting_id=meeting.id,
        kind=AlertKind.premise_break,
        verdict="Break",
        state=AlertState.open,
    )
    db.add_all([dec_item, alert])
    db.commit()

    resp = client.get("/meetings")
    assert resp.status_code == 200
    meetings = resp.json()
    found = next((m for m in meetings if m["id"] == meeting.id), None)
    assert found is not None
    # 1 proposed item + 1 open alert = 2 pending review
    assert found["pending_review_count"] >= 2


def test_unmapped_speakers_endpoint(client, db: Session):
    meeting = Meeting(
        title="Speaker Mapping Meeting",
        date=date(2026, 11, 21),
        project="Payments Revamp",
        transcript_ref="seed/speakers.vtt",
        status=MeetingStatus.uploaded,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    u1 = Utterance(meeting_id=meeting.id, idx=0, speaker_raw="UnknownSpeakerA", person_id=None, text="Hello")
    u2 = Utterance(meeting_id=meeting.id, idx=1, speaker_raw="UnknownSpeakerA", person_id=None, text="World")
    db.add_all([u1, u2])
    db.commit()

    resp = client.get(f"/meetings/{meeting.id}/unmapped-speakers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    speaker_a = next((s for s in data if s["speaker_raw"] == "UnknownSpeakerA"), None)
    assert speaker_a is not None
    assert speaker_a["count"] == 2


def test_config_and_demo_reset(client, db: Session):
    # GET /config
    resp = client.get("/config")
    assert resp.status_code == 200
    cfg = resp.json()
    assert "demo_mode" in cfg

    # POST /demo/reset
    resp_reset = client.post("/demo/reset")
    if cfg["demo_mode"]:
        assert resp_reset.status_code == 200
        assert resp_reset.json()["status"] == "ok"
    else:
        assert resp_reset.status_code == 403
