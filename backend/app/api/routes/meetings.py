from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Meeting, Utterance, Person
from app.schemas.schemas import MeetingRead, UtteranceRead
from app.services.ingestion import ingest_meeting, patch_meeting_speaker

router = APIRouter(prefix="/meetings", tags=["meetings"])


class PatchSpeakerRequest(BaseModel):
    speaker_raw: str
    person_id: int


class MeetingSummaryRead(MeetingRead):
    utterance_count: int
    unmapped_speakers_count: int


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
    try:
        content = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = file_bytes.decode("latin-1")

    filename = file.filename or "transcript.vtt"

    meeting = ingest_meeting(
        db=db,
        content=content,
        filename=filename,
        title=title,
        meeting_date=meeting_date,
        project=project,
        region=region,
        release=release,
    )
    return meeting


@router.get("", response_model=List[MeetingSummaryRead])
def list_meetings(db: Session = Depends(get_db)):
    """List all meetings with utterance counts and unmapped speaker flags."""
    meetings = db.query(Meeting).order_by(Meeting.date.desc()).all()
    results = []
    for m in meetings:
        utt_count = db.query(Utterance).filter_by(meeting_id=m.id).count()
        unmapped_count = (
            db.query(Utterance)
            .filter(Utterance.meeting_id == m.id, Utterance.person_id.is_(None))
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
            )
        )
    return results


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
