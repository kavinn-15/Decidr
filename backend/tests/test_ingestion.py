import io
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.models.models import Person, Meeting, Utterance, AuditLog
from app.services.ingestion import (
    parse_vtt,
    parse_srt,
    parse_txt,
    parse_json,
    map_speaker,
    ingest_meeting,
    patch_meeting_speaker,
)


def test_vtt_parsing():
    content = """WEBVTT

00:00:01.500 --> 00:00:04.200
Asha: Welcome everyone to the sprint planning.

00:00:04.500 --> 00:00:08.000
Ravi: Thanks Asha. I reviewed the gateway specs.
"""
    cues = parse_vtt(content)
    assert len(cues) == 2
    assert cues[0]["speaker_raw"] == "Asha"
    assert cues[0]["start_ts"] == 1.5
    assert cues[0]["text"] == "Welcome everyone to the sprint planning."
    assert cues[1]["speaker_raw"] == "Ravi"
    assert cues[1]["start_ts"] == 4.5


def test_srt_parsing():
    content = """1
00:00:01,500 --> 00:00:04,200
Asha: Welcome to the SRT meeting.

2
00:00:05,000 --> 00:00:08,500
Meera: Frontend is ready.
"""
    cues = parse_srt(content)
    assert len(cues) == 2
    assert cues[0]["speaker_raw"] == "Asha"
    assert cues[0]["start_ts"] == 1.5
    assert cues[1]["speaker_raw"] == "Meera"
    assert cues[1]["start_ts"] == 5.0


def test_txt_parsing():
    content = """[00:01:15.500] Karthik: Budget is approved.
Divya: QA suite is updated.
Sam: Contract is sent.
"""
    cues = parse_txt(content)
    assert len(cues) == 3
    assert cues[0]["speaker_raw"] == "Karthik"
    assert cues[0]["start_ts"] == 75.5
    assert cues[0]["text"] == "Budget is approved."
    assert cues[1]["speaker_raw"] == "Divya"
    assert cues[2]["speaker_raw"] == "Sam"


def test_json_parsing():
    content = """[
        {"speaker": "Asha", "text": "Starting JSON review.", "start": 2.5},
        {"speaker": "Ravi", "text": "Backend ready.", "start": 5.0}
    ]"""
    cues = parse_json(content)
    assert len(cues) == 2
    assert cues[0]["speaker_raw"] == "Asha"
    assert cues[0]["start_ts"] == 2.5
    assert cues[1]["speaker_raw"] == "Ravi"
    assert cues[1]["start_ts"] == 5.0


def test_speaker_fuzzy_matching(db):
    """
    Test speaker matching:
    1. Exact match
    2. Case-insensitive exact match
    3. First name match
    4. Initials match
    """
    p1 = Person(name="Asha Sharma", email="asha.s@test.com", tracker_id="ASHA-1")
    p2 = Person(name="Ravi Kumar", email="ravi.k@test.com", tracker_id="RAVI-1")
    db.add_all([p1, p2])
    db.commit()

    people = [p1, p2]

    # 1. Exact match
    pid, mapped = map_speaker("Asha Sharma", people)
    assert mapped is True
    assert pid == p1.id

    # 2. Case-insensitive match
    pid, mapped = map_speaker("ravi kumar", people)
    assert mapped is True
    assert pid == p2.id

    # 3. First name match
    pid, mapped = map_speaker("Asha", people)
    assert mapped is True
    assert pid == p1.id

    pid, mapped = map_speaker("Ravi", people)
    assert mapped is True
    assert pid == p2.id

    # 4. Initials match
    pid, mapped = map_speaker("AS", people)
    assert mapped is True
    assert pid == p1.id

    pid, mapped = map_speaker("RK", people)
    assert mapped is True
    assert pid == p2.id

    # 5. Unmapped speaker
    pid, mapped = map_speaker("Unknown Guest", people)
    assert mapped is False
    assert pid is None


def test_unmapped_speaker_flagged(db):
    """
    Assert that an unmapped speaker receives person_id=None and meeting is flagged.
    """
    person = Person(name="Asha", email="asha@test.com", tracker_id="A-1")
    db.add(person)
    db.commit()

    raw_transcript = """WEBVTT

00:00:01.000 --> 00:00:04.000
Asha: Welcome.

00:00:04.500 --> 00:00:08.000
Speaker 2: Who is speaking?
"""
    meeting = ingest_meeting(
        db=db,
        content=raw_transcript,
        filename="test_meeting.vtt",
        title="Test Unmapped Meeting",
        meeting_date=date(2026, 11, 2),
        project="Payments Revamp",
    )

    utterances = db.query(Utterance).filter_by(meeting_id=meeting.id).all()
    assert len(utterances) == 2
    assert utterances[0].person_id == person.id
    assert utterances[1].person_id is None
    assert utterances[1].speaker_raw == "Speaker 2"
    assert meeting.error == "Contains unmapped speaker(s)"


def test_patch_speaker_mapping(db):
    """
    Test patching unmapped speaker across all utterances in the meeting.
    Asserts utterances are updated and audit log is recorded.
    """
    p = Person(name="Sam Wilson", email="sam.w@test.com", tracker_id="SAM-1")
    db.add(p)
    db.commit()

    raw_transcript = """WEBVTT

00:00:01.000 --> 00:00:03.000
Vendor Rep: First point.

00:00:03.500 --> 00:00:06.000
Vendor Rep: Second point.
"""
    meeting = ingest_meeting(
        db=db,
        content=raw_transcript,
        filename="vendor_sync.vtt",
        title="Vendor Sync",
        meeting_date=date(2026, 11, 5),
        project="Payments Revamp",
    )

    # Both utterances currently unmapped
    utts = db.query(Utterance).filter_by(meeting_id=meeting.id).all()
    assert all(u.person_id is None for u in utts)

    # Patch mapping
    result = patch_meeting_speaker(
        db=db,
        meeting_id=meeting.id,
        speaker_raw="Vendor Rep",
        person_id=p.id,
        actor="test_user",
    )

    assert result["updated_utterances"] == 2
    assert result["remaining_unmapped"] == 0

    # Verify utterances updated
    db.refresh(meeting)
    assert meeting.error is None
    updated_utts = db.query(Utterance).filter_by(meeting_id=meeting.id).all()
    assert all(u.person_id == p.id for u in updated_utts)

    # Verify audit log entry
    audit_entry = (
        db.query(AuditLog)
        .filter_by(entity_type="meeting", entity_id=meeting.id, action="map_speaker")
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.actor == "test_user"
    assert audit_entry.after["person_id"] == p.id


def test_meetings_api_endpoints(client: TestClient, db):
    """
    Test POST /meetings, GET /meetings, GET /meetings/{id}/utterances, and PATCH /meetings/{id}/speakers.
    """
    p = Person(name="Asha", email="asha.api@test.com", tracker_id="API-1")
    db.add(p)
    db.commit()

    vtt_content = b"""WEBVTT

00:00:01.000 --> 00:00:03.000
Asha: API upload test.

00:00:03.500 --> 00:00:06.000
Guest: Need mapping.
"""
    # 1. POST /meetings
    res_post = client.post(
        "/meetings",
        data={
            "title": "API Uploaded Meeting",
            "date": "2026-11-21",
            "project": "Payments Revamp",
            "region": "India",
        },
        files={"file": ("meeting.vtt", io.BytesIO(vtt_content), "text/vtt")},
    )
    assert res_post.status_code == 201
    meeting_data = res_post.json()
    meeting_id = meeting_data["id"]
    assert meeting_data["title"] == "API Uploaded Meeting"

    # 2. GET /meetings
    res_list = client.get("/meetings")
    assert res_list.status_code == 200
    meetings = res_list.json()
    assert any(m["id"] == meeting_id for m in meetings)

    # 3. GET /meetings/{id}/utterances
    res_utts = client.get(f"/meetings/{meeting_id}/utterances")
    assert res_utts.status_code == 200
    utts = res_utts.json()
    assert len(utts) == 2
    assert utts[0]["speaker_raw"] == "Asha"
    assert utts[0]["is_unmapped"] is False
    assert utts[1]["speaker_raw"] == "Guest"
    assert utts[1]["is_unmapped"] is True

    # 4. PATCH /meetings/{id}/speakers
    res_patch = client.patch(
        f"/meetings/{meeting_id}/speakers",
        json={"speaker_raw": "Guest", "person_id": p.id},
    )
    assert res_patch.status_code == 200
    patch_result = res_patch.json()
    assert patch_result["updated_utterances"] == 1
    assert patch_result["remaining_unmapped"] == 0

    # Verify utterances are now all mapped
    res_utts_after = client.get(f"/meetings/{meeting_id}/utterances")
    utts_after = res_utts_after.json()
    assert all(not u["is_unmapped"] for u in utts_after)
