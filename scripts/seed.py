import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.db.session import engine, init_db, SessionLocal
from app.models.models import Person, Meeting, Utterance
from app.models.enums import MeetingStatus


def parse_vtt(content: str):
    """
    Parse a WebVTT file into cues containing idx, speaker, text, and start_ts.
    """
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
        full_text = " ".join(text_lines)
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
            "speaker": speaker,
            "text": text,
            "start_ts": start_ts,
        })
        idx += 1

    return cues


def seed_database():
    print("Starting database seeding...")
    init_db(engine)

    seed_dir = backend_path / "seed"
    roster_file = seed_dir / "roster.json"

    if not roster_file.exists():
        raise FileNotFoundError(f"Roster file not found at {roster_file}")

    with open(roster_file, "r", encoding="utf-8") as f:
        roster_data = json.load(f)

    session = SessionLocal()
    try:
        # 1. Seed Roster
        person_map = {}
        for p in roster_data:
            existing = session.query(Person).filter_by(email=p["email"]).first()
            if not existing:
                person = Person(
                    name=p["name"],
                    email=p["email"],
                    tracker_id=p["tracker_id"],
                    slack_id=p.get("slack_id"),
                )
                session.add(person)
                session.flush()
                person_map[person.name.lower()] = person.id
                print(f"Added person: {person.name} ({person.email})")
            else:
                person_map[existing.name.lower()] = existing.id

        session.commit()

        # 2. Seed Meetings and Utterances
        vtt_files = sorted(list(seed_dir.glob("m*.vtt")))
        meeting_titles = {
            "m1": "Payments Revamp Kickoff",
            "m2": "Payments Weekly Sync #1",
            "m3": "Payments Architecture & Timeline Sync",
            "m4": "Testing & Sandbox Review",
        }

        for vtt_path in vtt_files:
            filename = vtt_path.name
            match = re.match(r'(m\d+)_(\d{4}-\d{2}-\d{2})\.vtt', filename)
            if not match:
                continue

            meeting_code, date_str = match.groups()
            meeting_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            title = meeting_titles.get(meeting_code, f"Payments Revamp {meeting_code.upper()}")

            existing_meeting = session.query(Meeting).filter_by(
                title=title, date=meeting_date, project="Payments Revamp"
            ).first()

            if existing_meeting:
                print(f"Meeting '{title}' on {date_str} already exists. Skipping.")
                continue

            meeting = Meeting(
                title=title,
                date=meeting_date,
                project="Payments Revamp",
                region="India",
                release="v1.0",
                transcript_ref=str(vtt_path.name),
                status=MeetingStatus.uploaded,
            )
            session.add(meeting)
            session.flush()
            print(f"Created meeting: {meeting.title} (ID: {meeting.id}) on {meeting.date}")

            with open(vtt_path, "r", encoding="utf-8") as vf:
                vtt_content = vf.read()

            cues = parse_vtt(vtt_content)
            for cue in cues:
                speaker_raw = cue["speaker"]
                person_id = person_map.get(speaker_raw.lower())
                utterance = Utterance(
                    meeting_id=meeting.id,
                    idx=cue["idx"],
                    speaker_raw=speaker_raw,
                    person_id=person_id,
                    text=cue["text"],
                    start_ts=cue["start_ts"],
                )
                session.add(utterance)

            session.commit()
            print(f"  Inserted {len(cues)} utterances for {meeting.title}.")

        print("Seeding completed successfully.")

    except Exception as e:
        session.rollback()
        print(f"Seeding failed: {e}")
        raise e
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
