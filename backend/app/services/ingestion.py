import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.models import Meeting, Utterance, Person
from app.models.enums import MeetingStatus
from app.services.audit import log as audit_log


def parse_vtt(content: str) -> List[Dict[str, Any]]:
    """Parse WebVTT content into utterance dictionaries."""
    blocks = re.split(r'\n\s*\n', content.strip())
    cues = []
    idx = 0
    time_regex = re.compile(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})')

    for block in blocks:
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].startswith("WEBVTT"):
            lines = lines[1:]
            if not lines:
                continue

        ts_line_idx = -1
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line_idx = i
                break

        if ts_line_idx == -1:
            continue

        m = time_regex.search(lines[ts_line_idx])
        start_ts = None
        if m:
            hours, mins, secs, ms = map(int, m.groups()[:4])
            start_ts = hours * 3600.0 + mins * 60.0 + secs + ms / 1000.0

        text_lines = lines[ts_line_idx + 1:]
        full_text = " ".join(text_lines).strip()
        if not full_text:
            continue

        speaker = "Unknown"
        text = full_text
        if ":" in full_text:
            parts = full_text.split(":", 1)
            speaker = parts[0].strip()
            text = parts[1].strip()

        cues.append({
            "idx": idx,
            "speaker_raw": speaker,
            "text": text,
            "start_ts": start_ts,
        })
        idx += 1

    return cues


def parse_srt(content: str) -> List[Dict[str, Any]]:
    """Parse SubRip (.srt) content into utterance dictionaries."""
    blocks = re.split(r'\n\s*\n', content.strip())
    cues = []
    idx = 0
    time_regex = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})')

    for block in blocks:
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        if not lines:
            continue

        ts_line_idx = -1
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line_idx = i
                break

        if ts_line_idx == -1:
            continue

        m = time_regex.search(lines[ts_line_idx])
        start_ts = None
        if m:
            hours, mins, secs, ms = map(int, m.groups()[:4])
            start_ts = hours * 3600.0 + mins * 60.0 + secs + ms / 1000.0

        text_lines = lines[ts_line_idx + 1:]
        full_text = " ".join(text_lines).strip()
        if not full_text:
            continue

        speaker = "Unknown"
        text = full_text
        if ":" in full_text:
            parts = full_text.split(":", 1)
            speaker = parts[0].strip()
            text = parts[1].strip()

        cues.append({
            "idx": idx,
            "speaker_raw": speaker,
            "text": text,
            "start_ts": start_ts,
        })
        idx += 1

    return cues


def parse_txt(content: str) -> List[Dict[str, Any]]:
    """
    Parse plain text transcripts with lines like:
    'Asha: Good morning everyone.' or '[00:01:23] Asha: Hello'
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    cues = []
    idx = 0
    ts_speaker_regex = re.compile(r'^(?:\[(\d{1,2}:)?(\d{2}):(\d{2})(?:\.(\d{1,3}))?\]\s*)?([^:]+):\s*(.+)$')

    for line in lines:
        m = ts_speaker_regex.match(line)
        if m:
            hrs, mins, secs, ms, speaker, text = m.groups()
            start_ts = None
            if mins and secs:
                h = int(hrs.rstrip(":")) if hrs else 0
                s = int(secs)
                m_val = int(mins)
                msec = int(ms) if ms else 0
                start_ts = h * 3600.0 + m_val * 60.0 + s + (msec / 1000.0 if ms else 0.0)

            cues.append({
                "idx": idx,
                "speaker_raw": speaker.strip(),
                "text": text.strip(),
                "start_ts": start_ts,
            })
            idx += 1
        elif ":" in line:
            parts = line.split(":", 1)
            cues.append({
                "idx": idx,
                "speaker_raw": parts[0].strip(),
                "text": parts[1].strip(),
                "start_ts": None,
            })
            idx += 1
        else:
            cues.append({
                "idx": idx,
                "speaker_raw": "Unknown",
                "text": line,
                "start_ts": None,
            })
            idx += 1

    return cues


def parse_json(content: str) -> List[Dict[str, Any]]:
    """Parse JSON transcript: list of {speaker, text, start}."""
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError("JSON transcript must be a list of utterances.")

    cues = []
    for idx, item in enumerate(data):
        speaker = item.get("speaker") or item.get("speaker_raw") or "Unknown"
        text = item.get("text") or ""
        start_ts = item.get("start") or item.get("start_ts")
        if start_ts is not None:
            start_ts = float(start_ts)

        cues.append({
            "idx": idx,
            "speaker_raw": str(speaker).strip(),
            "text": str(text).strip(),
            "start_ts": start_ts,
        })
    return cues


def parse_transcript(content: str, filename: str) -> List[Dict[str, Any]]:
    """Detect format from filename extension or content and parse utterances."""
    lower_name = filename.lower()
    if lower_name.endswith(".vtt") or content.strip().startswith("WEBVTT"):
        return parse_vtt(content)
    elif lower_name.endswith(".srt"):
        return parse_srt(content)
    elif lower_name.endswith(".json") or content.strip().startswith("["):
        return parse_json(content)
    else:
        return parse_txt(content)


def map_speaker(speaker_raw: str, people: List[Person]) -> Tuple[Optional[int], bool]:
    """
    Match speaker_raw to the roster:
    1. Exact match
    2. Case-insensitive exact match
    3. First name match (e.g. 'Ravi' matches 'Ravi Kumar')
    4. Initials match (e.g. 'AK' matches 'Asha Kumar')
    Returns (person_id, is_mapped). Unmatched returns (None, False).
    """
    raw = speaker_raw.strip()
    raw_lower = raw.lower()

    # 1. Exact match
    for p in people:
        if p.name == raw:
            return p.id, True

    # 2. Case-insensitive match
    for p in people:
        if p.name.lower() == raw_lower:
            return p.id, True

    # 3. First name match
    for p in people:
        p_first = p.name.split()[0].lower()
        raw_first = raw.split()[0].lower()
        if p_first == raw_first or p_first == raw_lower or p.name.lower() == raw_first:
            return p.id, True

    # 4. Initials match (e.g. 'RS' -> 'Ravi Sharma')
    if len(raw) in (2, 3) and raw.isalpha():
        raw_upper = raw.upper()
        for p in people:
            initials = "".join([w[0].upper() for w in p.name.split() if w])
            if initials == raw_upper:
                return p.id, True

    # Unmapped speaker
    return None, False


def ingest_meeting(
    db: Session,
    content: str,
    filename: str,
    title: str,
    meeting_date: date,
    project: str,
    region: Optional[str] = None,
    release: Optional[str] = None,
    actor: str = "system",
) -> Meeting:
    """
    Ingest a transcript into Meeting and Utterance records.
    - Parses utterances
    - Maps speakers against Person roster
    - Flags unmapped speakers
    - Records audit log entry
    """
    # Create meeting in processing state
    meeting = Meeting(
        title=title,
        date=meeting_date,
        project=project,
        region=region,
        release=release,
        transcript_ref=filename,
        status=MeetingStatus.processing,
    )
    db.add(meeting)
    db.flush()

    # Parse transcript
    cues = parse_transcript(content, filename)
    people = db.query(Person).all()

    has_unmapped = False
    for cue in cues:
        person_id, is_mapped = map_speaker(cue["speaker_raw"], people)
        if not is_mapped:
            has_unmapped = True

        utterance = Utterance(
            meeting_id=meeting.id,
            idx=cue["idx"],
            speaker_raw=cue["speaker_raw"],
            person_id=person_id,
            text=cue["text"],
            start_ts=cue["start_ts"],
        )
        db.add(utterance)

    # Set status: review if speakers need mapping, else review/uploaded
    meeting.status = MeetingStatus.review
    if has_unmapped:
        meeting.error = "Contains unmapped speaker(s)"

    db.flush()

    # Log audit entry
    audit_log(
        actor=actor,
        action="ingest_meeting",
        entity_type="meeting",
        entity_id=meeting.id,
        before=None,
        after={
            "title": title,
            "date": str(meeting_date),
            "project": project,
            "utterances_count": len(cues),
            "has_unmapped_speakers": has_unmapped,
        },
        db=db,
    )

    db.commit()
    db.refresh(meeting)
    return meeting


def patch_meeting_speaker(
    db: Session,
    meeting_id: int,
    speaker_raw: str,
    person_id: int,
    actor: str = "user",
) -> Dict[str, Any]:
    """
    Map an unmapped speaker to a person across all utterances in the meeting.
    Writes an audit log entry.
    """
    meeting = db.query(Meeting).filter_by(id=meeting_id).first()
    if not meeting:
        raise ValueError(f"Meeting with ID {meeting_id} not found.")

    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise ValueError(f"Person with ID {person_id} not found.")

    utterances = (
        db.query(Utterance)
        .filter(Utterance.meeting_id == meeting_id, Utterance.speaker_raw == speaker_raw)
        .all()
    )

    count = len(utterances)
    for u in utterances:
        u.person_id = person_id

    # Check if there are remaining unmapped utterances
    remaining_unmapped = (
        db.query(Utterance)
        .filter(Utterance.meeting_id == meeting_id, Utterance.person_id.is_(None))
        .count()
    )
    if remaining_unmapped == 0:
        meeting.error = None

    db.flush()

    # Log audit entry
    audit_log(
        actor=actor,
        action="map_speaker",
        entity_type="meeting",
        entity_id=meeting.id,
        before={"speaker_raw": speaker_raw, "previous_person_id": None},
        after={"speaker_raw": speaker_raw, "person_id": person_id, "person_name": person.name, "updated_count": count},
        db=db,
    )

    db.commit()

    return {
        "meeting_id": meeting_id,
        "speaker_raw": speaker_raw,
        "person_id": person_id,
        "person_name": person.name,
        "updated_utterances": count,
        "remaining_unmapped": remaining_unmapped,
    }
