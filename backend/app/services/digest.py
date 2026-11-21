import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.models import (
    Person,
    Task,
    Decision,
    Premise,
    Alert,
    Link,
    Outbox,
    Utterance,
)
from app.models.enums import (
    TaskStatus,
    DecisionStatus,
    PremiseStatus,
    AlertState,
    AlertKind,
)

logger = logging.getLogger("decidr.digest")


def build_digest(
    person_id: int,
    as_of: Optional[date] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Builds personal weekly digest for a team member as of a given date.

    Sections returned:
    1. Due this week (Monday through Sunday relative to as_of)
    2. Overdue
    3. Decisions affecting you
    4. Conflicts and alerts needing your input
    5. Work resting on broken or shaky premises (NEW section)

    Invariants enforced:
    - Personal isolation: Digest NEVER lists tasks owned by anyone else.
    - All tasks resting on broken or shaky premises are surfaced with rationale.
    - Renders both HTML and plain text.
    """
    if db is None:
        from app.db.session import SessionLocal
        with SessionLocal() as session:
            return build_digest(person_id, as_of=as_of, db=session)

    person = db.get(Person, person_id)
    if not person:
        raise ValueError(f"Person #{person_id} not found")

    as_of_date = as_of or datetime.now(timezone.utc).date()

    # Week bounds: Monday of as_of week to Sunday
    start_of_week = as_of_date - timedelta(days=as_of_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # 1. Due This Week (strictly owned by person)
    due_this_week_tasks = (
        db.query(Task)
        .filter(
            Task.owner_id == person.id,
            Task.status.in_([TaskStatus.open, TaskStatus.at_risk]),
            Task.due_date >= start_of_week,
            Task.due_date <= end_of_week,
        )
        .order_by(Task.due_date.asc())
        .all()
    )

    # 2. Overdue Tasks (strictly owned by person)
    overdue_tasks = (
        db.query(Task)
        .filter(
            Task.owner_id == person.id,
            Task.status.in_([TaskStatus.open, TaskStatus.at_risk]),
            Task.due_date < as_of_date,
        )
        .order_by(Task.due_date.asc())
        .all()
    )

    # 3. Decisions Affecting You
    # Find all decisions linked to this person's tasks
    my_tasks = db.query(Task).filter(Task.owner_id == person.id).all()
    my_task_ids = [t.id for t in my_tasks]

    linked_decision_ids = {t.decision_id for t in my_tasks if t.decision_id is not None}

    # Also decisions connected via confirmed implements/depends_on links
    if my_task_ids:
        confirmed_links = (
            db.query(Link)
            .filter(
                Link.source_type == "task",
                Link.source_id.in_(my_task_ids),
                Link.target_type == "decision",
                Link.confirmed == True,
            )
            .all()
        )
        for lnk in confirmed_links:
            linked_decision_ids.add(lnk.target_id)

    decisions_affecting_you = []
    if linked_decision_ids:
        decisions_affecting_you = (
            db.query(Decision)
            .filter(Decision.id.in_(linked_decision_ids))
            .all()
        )

    # 4. Conflicts & Alerts Needing Input
    alerts_needing_input = []
    if linked_decision_ids:
        alerts_needing_input = (
            db.query(Alert)
            .filter(
                Alert.decision_id.in_(linked_decision_ids),
                Alert.state == AlertState.open,
            )
            .all()
        )

    # 5. Work Resting on Broken or Shaky Premises (NEW section)
    # Strictly for tasks owned by THIS person
    work_resting_on_broken_shaky: List[Dict[str, Any]] = []

    for task in my_tasks:
        if task.status in (TaskStatus.done, TaskStatus.cancelled):
            continue

        # Find linked decisions for this task
        task_decision_ids = set()
        if task.decision_id:
            task_decision_ids.add(task.decision_id)

        t_links = (
            db.query(Link)
            .filter(
                Link.source_type == "task",
                Link.source_id == task.id,
                Link.target_type == "decision",
                Link.confirmed == True,
            )
            .all()
        )
        for lnk in t_links:
            task_decision_ids.add(lnk.target_id)

        if not task_decision_ids:
            continue

        # Check premises belonging to these decisions
        premises = (
            db.query(Premise)
            .filter(Premise.decision_id.in_(task_decision_ids))
            .all()
        )

        for p in premises:
            if p.status in (PremiseStatus.broken, PremiseStatus.shaky):
                dec = db.get(Decision, p.decision_id)
                work_resting_on_broken_shaky.append({
                    "task_id": task.id,
                    "task_title": task.title,
                    "owner_name": person.name,
                    "owner_id": person.id,
                    "status": task.status.value,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "estimate_hours": task.estimate_hours,
                    "provisional": task.provisional,
                    "decision_id": dec.id if dec else p.decision_id,
                    "decision_text": dec.text if dec else f"Decision #{p.decision_id}",
                    "premise_id": p.id,
                    "premise_text": p.text,
                    "premise_status": p.status.value,
                    "reason": f"Underlying premise P{p.id} (\"{p.text}\") is {p.status.value.upper()}.",
                })
                break  # avoid duplicate task row if multiple premises broken

    # Format structured sections
    def _format_task(t: Task) -> Dict[str, Any]:
        return {
            "id": t.id,
            "title": t.title,
            "owner_name": person.name,
            "owner_id": person.id,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "status": t.status.value,
            "estimate_hours": t.estimate_hours,
            "provisional": t.provisional,
            "tracker_ref": t.tracker_ref,
        }

    sections_data = {
        "due_this_week": [_format_task(t) for t in due_this_week_tasks],
        "overdue": [_format_task(t) for t in overdue_tasks],
        "decisions_affecting_you": [
            {
                "id": d.id,
                "text": d.text,
                "status": d.status.value,
                "scope_project": d.scope_project,
                "scope_region": d.scope_region,
            }
            for d in decisions_affecting_you
        ],
        "alerts_needing_input": [
            {
                "id": a.id,
                "kind": a.kind.value,
                "verdict": a.verdict,
                "explanation": a.explanation,
                "decision_id": a.decision_id,
            }
            for a in alerts_needing_input
        ],
        "work_resting_on_broken_or_shaky_premises": work_resting_on_broken_shaky,
    }

    # Render Plain Text
    text_lines = [
        f"DECIDR WEEKLY DIGEST — {person.name}",
        f"Week of {start_of_week.strftime('%B %d, %Y')} to {end_of_week.strftime('%B %d, %Y')} (As of {as_of_date.isoformat()})",
        "=" * 60,
        "",
        "1. DUE THIS WEEK",
        "-" * 30,
    ]
    if sections_data["due_this_week"]:
        for t in sections_data["due_this_week"]:
            text_lines.append(f"• [Due {t['due_date']}] {t['title']} (Status: {t['status']}, Ref: {t['tracker_ref'] or 'N/A'})")
    else:
        text_lines.append("No tasks due this week.")

    text_lines.extend(["", "2. OVERDUE TASKS", "-" * 30])
    if sections_data["overdue"]:
        for t in sections_data["overdue"]:
            text_lines.append(f"• [OVERDUE {t['due_date']}] {t['title']} (Ref: {t['tracker_ref'] or 'N/A'})")
    else:
        text_lines.append("No overdue tasks.")

    text_lines.extend(["", "3. DECISIONS AFFECTING YOU", "-" * 30])
    if sections_data["decisions_affecting_you"]:
        for d in sections_data["decisions_affecting_you"]:
            text_lines.append(f"• D{d['id']}: {d['text']} ({d['status']}, Region: {d['scope_region'] or 'Global'})")
    else:
        text_lines.append("No linked decisions.")

    text_lines.extend(["", "4. CONFLICTS & ALERTS NEEDING INPUT", "-" * 30])
    if sections_data["alerts_needing_input"]:
        for a in sections_data["alerts_needing_input"]:
            text_lines.append(f"• Alert #{a['id']} ({a['kind']}): {a['verdict']} — {a['explanation']}")
    else:
        text_lines.append("No active alerts.")

    text_lines.extend(["", "5. WORK RESTING ON BROKEN OR SHAKY PREMISES", "-" * 30])
    if sections_data["work_resting_on_broken_or_shaky_premises"]:
        for w in sections_data["work_resting_on_broken_or_shaky_premises"]:
            text_lines.append(
                f"⚠️ [Task #{w['task_id']}] {w['task_title']}\n"
                f"   Premise: P{w['premise_id']} \"{w['premise_text']}\" is {w['premise_status'].upper()}\n"
                f"   Decision: D{w['decision_id']} \"{w['decision_text']}\"\n"
                f"   Reason: {w['reason']}"
            )
    else:
        text_lines.append("All your current work rests on verified holding premises.")

    plain_text = "\n".join(text_lines)

    # Render HTML
    html_markup = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Decidr Weekly Digest for {person.name}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; color: #1e293b; margin: 0; padding: 24px; background: #f8fafc; }}
    .container {{ max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
    .header {{ background: #0f172a; color: #ffffff; padding: 24px; }}
    .header h1 {{ margin: 0 0 6px 0; font-size: 20px; font-weight: 700; }}
    .header p {{ margin: 0; font-size: 13px; color: #94a3b8; }}
    .section {{ padding: 20px 24px; border-bottom: 1px solid #e2e8f0; }}
    .section:last-child {{ border-bottom: none; }}
    .section-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 12px; }}
    .task-item {{ padding: 10px 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; font-size: 13px; }}
    .alert-box {{ background: #fff1f2; border: 1px solid #fecdd3; border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; font-size: 13px; color: #881337; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
    .badge-overdue {{ background: #fee2e2; color: #991b1b; }}
    .badge-broken {{ background: #fecdd3; color: #be123c; }}
    .badge-shaky {{ background: #fef3c7; color: #b45309; }}
    .footer {{ padding: 16px 24px; font-size: 12px; color: #94a3b8; text-align: center; background: #f8fafc; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Weekly Digest: {person.name}</h1>
      <p>Week of {start_of_week.strftime('%B %d, %Y')} to {end_of_week.strftime('%B %d, %Y')}</p>
    </div>

    <!-- 5. Work Resting on Broken or Shaky Premises (Surfaced on top if present) -->
    {f'''
    <div class="section" style="background: #fff5f5;">
      <div class="section-title" style="color: #be123c;">⚠️ Work Resting on Broken or Shaky Premises</div>
      {"".join(f"""
      <div class="alert-box">
        <strong>Task #{w['task_id']}: {w['task_title']}</strong><br>
        <span class="badge badge-{w['premise_status']}">{w['premise_status']}</span>
        <span>{w['reason']}</span>
      </div>
      """ for w in sections_data['work_resting_on_broken_or_shaky_premises'])}
    </div>
    ''' if sections_data['work_resting_on_broken_or_shaky_premises'] else ''}

    <!-- 1. Due This Week -->
    <div class="section">
      <div class="section-title">Due This Week</div>
      {f'''
      {"".join(f"""
      <div class="task-item">
        <strong>{t['title']}</strong> — Due {t['due_date']}
        <span class="badge" style="background:#e0f2fe; color:#0369a1;">{t['status']}</span>
      </div>
      """ for t in sections_data['due_this_week'])}
      ''' if sections_data['due_this_week'] else '<p style="color:#64748b; font-size:13px; margin:0;">No tasks due this week.</p>'}
    </div>

    <!-- 2. Overdue Tasks -->
    <div class="section">
      <div class="section-title">Overdue Tasks</div>
      {f'''
      {"".join(f"""
      <div class="task-item" style="border-left: 3px solid #ef4444;">
        <span class="badge badge-overdue">Overdue</span>
        <strong>{t['title']}</strong> (Due {t['due_date']})
      </div>
      """ for t in sections_data['overdue'])}
      ''' if sections_data['overdue'] else '<p style="color:#64748b; font-size:13px; margin:0;">No overdue tasks.</p>'}
    </div>

    <!-- 3. Decisions Affecting You -->
    <div class="section">
      <div class="section-title">Decisions Affecting You</div>
      {f'''
      {"".join(f"""
      <div class="task-item">
        <strong>D{d['id']}: {d['text']}</strong> ({d['status']})
      </div>
      """ for d in sections_data['decisions_affecting_you'])}
      ''' if sections_data['decisions_affecting_you'] else '<p style="color:#64748b; font-size:13px; margin:0;">No decisions linked to your current work.</p>'}
    </div>

    <div class="footer">
      Decidr Enterprise Decision Safety Platform • Automatically generated for {person.email}
    </div>
  </div>
</body>
</html>"""

    return {
        "person_id": person.id,
        "person_name": person.name,
        "person_email": person.email,
        "as_of": as_of_date.isoformat(),
        "sections": sections_data,
        "html": html_markup,
        "text": plain_text,
        "rendered_html": html_markup,
        "rendered_text": plain_text,
    }


def generate_and_schedule_weekly_digests(
    db: Session,
    as_of: Optional[date] = None,
) -> List[Outbox]:
    """
    Weekly cron runner (Mondays 09:00).
    Builds personal digests for all people and schedules them into the outbox.
    """
    as_of_date = as_of or datetime.now(timezone.utc).date()
    people = db.query(Person).all()
    created_outboxes: List[Outbox] = []

    for person in people:
        digest = build_digest(person.id, as_of=as_of_date, db=db)
        outbox = Outbox(
            channel="email",
            to_addr=person.email,
            subject=f"[Decidr Weekly Digest] Your priorities and decision impacts for week of {as_of_date.isoformat()}",
            body=digest["html"],
            created_at=datetime.now(timezone.utc),
            sent=True,
        )
        db.add(outbox)
        created_outboxes.append(outbox)

    db.commit()
    return created_outboxes
