from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Person, Task, Outbox, Reminder
from app.models.enums import TaskStatus, ReminderState
from app.services.reminders import run_reminders, create_task_reminders
from app.services.digest import build_digest, generate_and_schedule_weekly_digests

router = APIRouter(tags=["reminders_digest"])


@router.get("/people")
def get_people_list(db: Session = Depends(get_db)):
    """
    Returns list of people for person selector and roster assignment.
    """
    people = db.query(Person).order_by(Person.name.asc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "email": p.email,
            "tracker_id": p.tracker_id,
            "slack_id": p.slack_id,
        }
        for p in people
    ]


@router.get("/digest/{person_id}")
def get_person_digest(
    person_id: int,
    as_of: Optional[str] = Query(None, description="Simulated reference date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Returns weekly digest preview for a person as of a reference date.
    """
    as_of_d: Optional[date] = None
    if as_of:
        try:
            as_of_d = date.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for as_of, expected YYYY-MM-DD")

    try:
        digest = build_digest(person_id=person_id, as_of=as_of_d, db=db)
        return digest
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/admin/run-reminders")
def trigger_run_reminders(
    now: Optional[str] = Query(None, description="Simulated current timestamp ISO format"),
    db: Session = Depends(get_db),
):
    """
    Trigger scheduled reminder dispatch, with optional simulated 'now' timestamp.
    """
    now_dt: Optional[datetime] = None
    if now:
        try:
            # Handle ISO string with or without Z
            cleaned_now = now.replace("Z", "+00:00")
            now_dt = datetime.fromisoformat(cleaned_now)
            if now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=timezone.utc)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid ISO timestamp format for now")

    result = run_reminders(db=db, now=now_dt)
    return result


@router.post("/admin/run-digest")
def trigger_run_digest(
    as_of: Optional[str] = Query(None, description="Simulated reference date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Trigger weekly digest dispatch and write to outbox for all team members.
    """
    as_of_d: Optional[date] = None
    if as_of:
        try:
            as_of_d = date.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for as_of, expected YYYY-MM-DD")

    created = generate_and_schedule_weekly_digests(db=db, as_of=as_of_d)
    return {
        "status": "scheduled",
        "digests_created": len(created),
        "as_of": (as_of_d or datetime.now(timezone.utc).date()).isoformat(),
    }


@router.get("/outbox")
def get_outbox_items(
    channel: Optional[str] = Query(None, description="Filter by channel (email, slack)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Returns newest-first list of outbound messages stored in outbox table.
    """
    query = db.query(Outbox)
    if channel:
        query = query.filter(Outbox.channel == channel)
    items = query.order_by(Outbox.id.desc()).limit(limit).all()

    return [
        {
            "id": item.id,
            "channel": item.channel,
            "to_addr": item.to_addr,
            "subject": item.subject,
            "body": item.body,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "sent": item.sent,
        }
        for item in items
    ]


@router.get("/my-week/{person_id}")
def get_my_week_data(
    person_id: int,
    as_of: Optional[str] = Query(None, description="Simulated reference date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Returns tasks for a person grouped by day of the week, overdue list, and broken/shaky premises items.
    """
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail=f"Person #{person_id} not found")

    as_of_d: date = datetime.now(timezone.utc).date()
    if as_of:
        try:
            as_of_d = date.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for as_of, expected YYYY-MM-DD")

    digest = build_digest(person_id=person.id, as_of=as_of_d, db=db)

    # Compute 7 days of the week starting Monday
    start_of_week = as_of_d - timedelta(days=as_of_d.weekday())
    days_data = []

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i in range(7):
        current_day = start_of_week + timedelta(days=i)
        # Tasks on this day
        tasks_on_day = (
            db.query(Task)
            .filter(
                Task.owner_id == person.id,
                Task.due_date == current_day,
            )
            .order_by(Task.id.asc())
            .all()
        )

        days_data.append({
            "day_name": day_names[i],
            "date": current_day.isoformat(),
            "is_today": current_day == as_of_d,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "status": t.status.value,
                    "estimate_hours": t.estimate_hours,
                    "provisional": t.provisional,
                    "at_risk": t.status == TaskStatus.at_risk,
                    "needs_owner": t.owner_id is None,
                    "tracker_ref": t.tracker_ref,
                    "tracker_url": t.tracker_url,
                }
                for t in tasks_on_day
            ],
        })

    return {
        "person": {
            "id": person.id,
            "name": person.name,
            "email": person.email,
            "tracker_id": person.tracker_id,
        },
        "person_id": person.id,
        "person_name": person.name,
        "as_of": as_of_d.isoformat(),
        "start_of_week": start_of_week.isoformat(),
        "end_of_week": (start_of_week + timedelta(days=6)).isoformat(),
        "days": days_data,
        "week_schedule": days_data,
        "overdue": digest["sections"]["overdue"],
        "shaky_broken": digest["sections"]["work_resting_on_broken_or_shaky_premises"],
        "broken_shaky_work": digest["sections"]["work_resting_on_broken_or_shaky_premises"],
        "digest_preview": digest,
    }
