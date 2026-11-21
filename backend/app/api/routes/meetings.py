from datetime import date
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.enums import MeetingStatus, ItemType, ReviewState, AlertState
from app.models.models import Meeting, Utterance, Person, Item, Alert
from app.schemas.schemas import MeetingRead, UtteranceRead, PersonRead
from app.services.ingestion import ingest_meeting, patch_meeting_speaker
from app.services.extraction import extract_meeting_items

router = APIRouter(prefix="/meetings", tags=["meetings"])


class PatchSpeakerRequest(BaseModel):
    speaker_raw: str
    person_id: int


class MeetingSummaryRead(MeetingRead):
    utterance_count: int
    unmapped_speakers_count: int
    pending_review_count: int = 0
    decisions_count: int = 0
    actions_count: int = 0


class UtteranceDetailRead(UtteranceRead):
    speaker_name: Optional[str] = None
    is_unmapped: bool


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    file: UploadFile = File(...),
    title: str = Form(...),
    date_val: str = Form(..., alias="date"),
    project: str = Form(...),
    region: Optional[str] = Form(None),
    release: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload and ingest a meeting transcript file (.vtt, .srt, .txt, .json).
    Parses utterances and maps speakers to roster.
    """
    try:
        meeting_date = date.fromisoformat(date_val)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date format: '{date_val}'. Expected YYYY-MM-DD.",
        )

    file_bytes = await file.read()
    if not file_bytes or not file_bytes.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript file is empty.",
        )

    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Transcript file exceeds maximum allowed size (5 MB).",
        )

    try:
        content = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = file_bytes.decode("latin-1")

    raw_filename = file.filename or "transcript.vtt"
    sanitized_filename = Path(raw_filename).name
    ext = Path(sanitized_filename).suffix.lower()
    allowed_exts = {".vtt", ".srt", ".txt", ".json"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed extensions: .vtt, .srt, .txt, .json",
        )

    meeting = ingest_meeting(
        db=db,
        content=content,
        filename=sanitized_filename,
        title=title,
        meeting_date=meeting_date,
        project=project,
        region=region,
        release=release,
    )
    return meeting


@router.get("", response_model=List[MeetingSummaryRead])
def list_meetings(db: Session = Depends(get_db)):
    """List all meetings with utterance counts, unmapped speaker flags, and pending review counts."""
    meetings = db.query(Meeting).order_by(Meeting.date.desc()).all()
    results = []
    for m in meetings:
        utt_count = db.query(Utterance).filter_by(meeting_id=m.id).count()
        unmapped_count = (
            db.query(Utterance)
            .filter(Utterance.meeting_id == m.id, Utterance.person_id.is_(None))
            .count()
        )
        proposed_items = (
            db.query(Item)
            .filter(Item.meeting_id == m.id, Item.review_state == ReviewState.proposed)
            .count()
        )
        open_alerts = (
            db.query(Alert)
            .filter(Alert.meeting_id == m.id, Alert.state == AlertState.open)
            .count()
        )
        dec_count = (
            db.query(Item)
            .filter(Item.meeting_id == m.id, Item.type == ItemType.decision)
            .count()
        )
        act_count = (
            db.query(Item)
            .filter(Item.meeting_id == m.id, Item.type == ItemType.action)
            .count()
        )
        results.append(
            MeetingSummaryRead(
                id=m.id,
                title=m.title,
                date=m.date,
                project=m.project,
                region=m.region,
                release=m.release,
                transcript_ref=m.transcript_ref,
                status=m.status,
                error=m.error,
                utterance_count=utt_count,
                unmapped_speakers_count=unmapped_count,
                pending_review_count=proposed_items + open_alerts,
                decisions_count=dec_count,
                actions_count=act_count,
            )
        )
    return results


@router.get("/roster/people", response_model=List[PersonRead])
def get_roster_people(db: Session = Depends(get_db)):
    """Get all roster people for speaker or owner assignment."""
    return db.query(Person).order_by(Person.name.asc()).all()


@router.get("/{meeting_id}/unmapped-speakers")
def get_meeting_unmapped_speakers(meeting_id: int, db: Session = Depends(get_db)):
    """Get list of distinct unmapped speakers in this meeting with utterance counts."""
    rows = (
        db.query(Utterance.speaker_raw, func.count(Utterance.id))
        .filter(Utterance.meeting_id == meeting_id, Utterance.person_id.is_(None))
        .group_by(Utterance.speaker_raw)
        .all()
    )
    return [{"speaker_raw": r[0], "count": r[1]} for r in rows]


@router.get("/{meeting_id}", response_model=MeetingRead)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Get single meeting details."""
    meeting = db.query(Meeting).filter_by(id=meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


@router.get("/{meeting_id}/utterances", response_model=List[UtteranceDetailRead])
def get_meeting_utterances(meeting_id: int, db: Session = Depends(get_db)):
    """Get timeline of utterances for a meeting with speaker resolution."""
    meeting = db.query(Meeting).filter_by(id=meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    utterances = (
        db.query(Utterance)
        .filter_by(meeting_id=meeting_id)
        .order_by(Utterance.idx.asc())
        .all()
    )

    results = []
    for u in utterances:
        person_name = u.person.name if u.person else None
        results.append(
            UtteranceDetailRead(
                id=u.id,
                meeting_id=u.meeting_id,
                idx=u.idx,
                speaker_raw=u.speaker_raw,
                person_id=u.person_id,
                text=u.text,
                start_ts=u.start_ts,
                speaker_name=person_name,
                is_unmapped=u.person_id is None,
            )
        )
    return results


def run_extraction_in_background(meeting_id: int):
    """Background task runner for meeting extraction."""
    from app.main import app
    from app.services.premise_watch import watch_meeting_utterances
    if get_db in app.dependency_overrides:
        override = app.dependency_overrides[get_db]
        session_gen = override()
        if hasattr(session_gen, "__next__"):
            db = next(session_gen)
            extract_meeting_items(db, meeting_id, actor="background_task")
            watch_meeting_utterances(db, meeting_id)
        else:
            extract_meeting_items(session_gen, meeting_id, actor="background_task")
            watch_meeting_utterances(session_gen, meeting_id)
        return

    with SessionLocal() as db:
        extract_meeting_items(db, meeting_id, actor="background_task")
        watch_meeting_utterances(db, meeting_id)


@router.post("/{meeting_id}/process")
def process_meeting(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Run two-pass extraction on meeting transcript in the background.
    Status transitions: uploaded -> processing -> review (or failed).
    """
    meeting = db.query(Meeting).filter_by(id=meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    meeting.status = MeetingStatus.processing
    db.commit()

    background_tasks.add_task(run_extraction_in_background, meeting_id)

    return {
        "meeting_id": meeting_id,
        "status": "processing",
        "message": "Extraction process started in the background.",
    }


@router.patch("/{meeting_id}/speakers")
def map_unmapped_speaker(
    meeting_id: int,
    payload: PatchSpeakerRequest,
    db: Session = Depends(get_db),
):
    """
    Map an unmapped speaker to a person across the entire meeting.
    Writes an append-only audit log entry.
    """
    try:
        result = patch_meeting_speaker(
            db=db,
            meeting_id=meeting_id,
            speaker_raw=payload.speaker_raw,
            person_id=payload.person_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{meeting_id}", status_code=status.HTTP_200_OK)
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
):
    """
    Privacy & Right-to-be-Forgotten Endpoint (Task 17 Requirement 5).
    Removes transcript text and all derived items (utterances, decisions, premises, tasks, links, alerts),
    keeping ONLY a non-content append-only audit entry.
    """
    from app.models.models import Decision, DecisionVersion, Premise, Task, Link, Alert, ChangeProposal, ChangeAction
    from app.services.audit import log as audit_log

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting #{meeting_id} not found",
        )

    # 1. Delete derived alerts and change proposals
    alerts = db.query(Alert).filter(Alert.meeting_id == meeting_id).all()
    for a in alerts:
        if a.proposal_id:
            db.query(ChangeAction).filter(ChangeAction.proposal_id == a.proposal_id).delete(synchronize_session=False)
            db.query(ChangeProposal).filter(ChangeProposal.id == a.proposal_id).delete(synchronize_session=False)
        db.delete(a)

    # 2. Delete derived items, tasks, decisions, premises, links
    items = db.query(Item).filter(Item.meeting_id == meeting_id).all()
    for item in items:
        # Tasks linked to item
        tasks = db.query(Task).filter(Task.item_id == item.id).all()
        for t in tasks:
            db.query(Link).filter((Link.source_type == "task") & (Link.source_id == t.id)).delete(synchronize_session=False)
            db.query(Link).filter((Link.target_type == "task") & (Link.target_id == t.id)).delete(synchronize_session=False)
            db.delete(t)

        # Decisions linked to item
        decs = db.query(Decision).filter(Decision.item_id == item.id).all()
        for d in decs:
            db.query(Premise).filter(Premise.decision_id == d.id).delete(synchronize_session=False)
            db.query(DecisionVersion).filter(DecisionVersion.decision_id == d.id).delete(synchronize_session=False)
            db.query(Link).filter((Link.source_type == "decision") & (Link.source_id == d.id)).delete(synchronize_session=False)
            db.query(Link).filter((Link.target_type == "decision") & (Link.target_id == d.id)).delete(synchronize_session=False)
            db.delete(d)

        db.delete(item)

    # 3. Delete raw dialogue utterances (transcript text)
    db.query(Utterance).filter(Utterance.meeting_id == meeting_id).delete(synchronize_session=False)

    # 4. Remove meeting record
    db.delete(meeting)
    db.commit()

    # 5. Non-content append-only audit entry (Invariant 3)
    audit_log(
        actor="privacy_officer",
        action="delete_meeting",
        entity_type="meeting",
        entity_id=meeting_id,
        before=None,
        after={
            "deleted": True,
            "title_redacted": True,
            "transcript_purged": True,
            "derived_items_purged": True,
            "retained_content": "none",
        },
        db=db,
    )

    return {
        "status": "purged",
        "meeting_id": meeting_id,
        "message": "Transcript text and derived items permanently removed. Non-content audit log preserved.",
    }

