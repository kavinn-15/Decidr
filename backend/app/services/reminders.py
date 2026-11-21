import logging
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    Reminder,
    Task,
    Person,
    Outbox,
    Decision,
    Premise,
    Alert,
    Link,
)
from app.models.enums import (
    ReminderKind,
    ReminderState,
    ReminderChannel,
    PremiseStatus,
    TaskStatus,
    AlertKind,
    AlertState,
)

logger = logging.getLogger("decidr.reminders")


def _get_configured_timezone() -> ZoneInfo:
    try:
        tz_name = settings.TIMEZONE or "UTC"
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def create_task_reminders(
    db: Session,
    task: Task,
    timezone_str: Optional[str] = None,
) -> List[Reminder]:
    """
    Creates reminders at 3 days before, 1 day before, and morning-of (08:00 in configurable timezone)
    for a task with a due date.
    """
    if not task.due_date:
        return []

    try:
        tz = ZoneInfo(timezone_str) if timezone_str else _get_configured_timezone()
    except Exception:
        tz = ZoneInfo("UTC")

    due_d = task.due_date

    # Compute target 08:00 datetimes in configured timezone, then convert to UTC
    # 1. Morning of (08:00)
    dt_morning_local = datetime(due_d.year, due_d.month, due_d.day, 8, 0, 0, tzinfo=tz)
    dt_morning_utc = dt_morning_local.astimezone(timezone.utc)

    # 2. 1 day before (08:00)
    d_1d = due_d - timedelta(days=1)
    dt_1d_local = datetime(d_1d.year, d_1d.month, d_1d.day, 8, 0, 0, tzinfo=tz)
    dt_1d_utc = dt_1d_local.astimezone(timezone.utc)

    # 3. 3 days before (08:00)
    d_3d = due_d - timedelta(days=3)
    dt_3d_local = datetime(d_3d.year, d_3d.month, d_3d.day, 8, 0, 0, tzinfo=tz)
    dt_3d_utc = dt_3d_local.astimezone(timezone.utc)

    reminder_defs = [
        (ReminderKind.three_day, dt_3d_utc),
        (ReminderKind.one_day, dt_1d_utc),
        (ReminderKind.morning, dt_morning_utc),
    ]

    created: List[Reminder] = []
    for kind, due_dt in reminder_defs:
        # Avoid creating duplicates if reminder of same kind already exists for this task
        existing = (
            db.query(Reminder)
            .filter(Reminder.task_id == task.id, Reminder.kind == kind)
            .first()
        )
        if not existing:
            rem = Reminder(
                task_id=task.id,
                kind=kind,
                due_at=due_dt,
                state=ReminderState.pending,
                channel=ReminderChannel.email,
                pause_reason=None,
            )
            db.add(rem)
            created.append(rem)

    db.flush()
    return created


def check_task_premise_shaky(db: Session, task: Task) -> bool:
    """
    Returns True if any premise upon which this task depends is 'shaky' or has an unconfirmed break alert.
    """
    # 1. Direct decision linked to task
    decision_ids: set[int] = set()
    if task.decision_id:
        decision_ids.add(task.decision_id)

    # 2. Decisions connected via confirmed implements links
    links = (
        db.query(Link)
        .filter(
            Link.source_type == "task",
            Link.source_id == task.id,
            Link.target_type == "decision",
            Link.confirmed == True,
        )
        .all()
    )
    for lnk in links:
        decision_ids.add(lnk.target_id)

    if not decision_ids:
        return False

    # Check premises belonging to these decisions
    premises = (
        db.query(Premise)
        .filter(Premise.decision_id.in_(decision_ids))
        .all()
    )
    for p in premises:
        if p.status in (PremiseStatus.shaky, PremiseStatus.broken):
            return True

    # Check open premise_break alerts for these premises
    premise_ids = [p.id for p in premises]
    if premise_ids:
        open_alerts = (
            db.query(Alert)
            .filter(
                Alert.premise_id.in_(premise_ids),
                Alert.state == AlertState.open,
                Alert.kind == AlertKind.premise_break,
            )
            .first()
        )
        if open_alerts:
            return True

    return False


def send_outbound_notification(
    channel: str,
    to_addr: str,
    subject: str,
    body: str,
    db: Session,
) -> Outbox:
    """
    Writes a row to the outbox table, and sends via SMTP/Resend and/or Slack if configured.
    """
    outbox = Outbox(
        channel=channel,
        to_addr=to_addr,
        subject=subject,
        body=body,
        created_at=datetime.now(timezone.utc),
        sent=True,
    )
    db.add(outbox)
    db.flush()

    # 1. Real email via Resend
    if settings.RESEND_API_KEY:
        try:
            import httpx
            httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": settings.SMTP_FROM,
                    "to": [to_addr],
                    "subject": subject,
                    "text": body,
                },
                timeout=5.0,
            )
        except Exception as e:
            logger.warning(f"Resend notification dispatch failed: {e}")

    # 2. Real email via SMTP
    elif settings.SMTP_HOST:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to_addr
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM, [to_addr], msg.as_string())
        except Exception as e:
            logger.warning(f"SMTP notification dispatch failed: {e}")

    # 3. Slack Webhook
    if settings.SLACK_WEBHOOK_URL:
        try:
            import httpx
            httpx.post(
                settings.SLACK_WEBHOOK_URL,
                json={"text": f"*{subject}*\n{body}"},
                timeout=5.0,
            )
        except Exception as e:
            logger.warning(f"Slack webhook notification dispatch failed: {e}")

    return outbox


def run_reminders(
    db: Session,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    APScheduler job / simulation runner for pending task reminders.
    - Runs every 15 minutes.
    - Each reminder sends at most once.
    - Paused reminders are never sent.
    - If a task's premise is shaky, adds warning text.
    """
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    # Invariant: Query pending reminders whose due_at <= now and pause_reason is None
    pending_reminders = (
        db.query(Reminder)
        .join(Task)
        .filter(
            Reminder.state == ReminderState.pending,
            Reminder.due_at <= now_dt,
            Reminder.pause_reason == None,
        )
        .all()
    )

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for rem in pending_reminders:
        # Paused reminders are strictly skipped (Invariant)
        if rem.state in (ReminderState.paused, ReminderState.cancelled) or rem.pause_reason is not None:
            skipped_count += 1
            continue

        task = rem.task
        if not task:
            rem.state = ReminderState.skipped
            skipped_count += 1
            continue

        # If task is done or cancelled, skip sending reminder
        if task.status in (TaskStatus.done, TaskStatus.cancelled):
            rem.state = ReminderState.skipped
            skipped_count += 1
            continue

        owner = task.owner
        owner_name = owner.name if owner else "Assignee"
        to_addr = owner.email if (owner and owner.email) else "unassigned@decidr.local"

        # Check if underlying premise is shaky / broken
        is_shaky = check_task_premise_shaky(db, task)

        kind_label = (
            "in 3 days"
            if rem.kind == ReminderKind.three_day
            else "tomorrow"
            if rem.kind == ReminderKind.one_day
            else "today"
        )
        due_date_str = task.due_date.isoformat() if task.due_date else "soon"
        subject = f"[Decidr Reminder] Task due {kind_label}: {task.title}"

        shaky_notice = ""
        if is_shaky:
            shaky_notice = "\n\nThe reason for this task may no longer hold; please review."

        body = (
            f"Hello {owner_name},\n\n"
            f"This is an automated reminder that your task \"{task.title}\" is due {kind_label} ({due_date_str}).\n\n"
            f"Task Details:\n"
            f"- Status: {task.status.value}\n"
            f"- Provisional: {task.provisional}\n"
            f"- Estimate: {task.estimate_hours or 'N/A'} hours\n"
            f"- External Ticket: {task.tracker_ref or 'None'}\n"
            f"{shaky_notice}\n\n"
            f"— Decidr Change Safety Platform"
        )

        try:
            send_outbound_notification(
                channel="email",
                to_addr=to_addr,
                subject=subject,
                body=body,
                db=db,
            )
            # Mark sent (Invariant: sends at most once)
            rem.state = ReminderState.sent
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to dispatch reminder #{rem.id}: {e}")
            failed_count += 1

    db.commit()

    return {
        "now": now_dt.isoformat(),
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "processed_count": len(pending_reminders),
    }
