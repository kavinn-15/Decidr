from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.models import TrackerTicket
from app.trackers.base import BaseTracker


class MockTracker(BaseTracker):
    """
    In-database mock tracker storing tickets in `tracker_tickets` table.
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_session(self) -> Session:
        return self._db if self._db is not None else SessionLocal()

    def find_by_key(self, idempotency_key: str) -> Optional[str]:
        if not idempotency_key:
            return None
        session = self._get_session()
        should_close = self._db is None
        try:
            ticket = (
                session.query(TrackerTicket)
                .filter(TrackerTicket.idempotency_key == idempotency_key)
                .first()
            )
            return ticket.ticket_ref if ticket else None
        finally:
            if should_close:
                session.close()

    def create_issue(
        self,
        title: str,
        body: str,
        assignee: Optional[str] = None,
        due_date: Optional[str] = None,
        labels: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, str]:
        if idempotency_key:
            existing = self.find_by_key(idempotency_key)
            if existing:
                return {"ref": existing, "url": f"/mock-tracker#{existing}"}

        session = self._get_session()
        should_close = self._db is None
        try:
            count = session.query(func.count(TrackerTicket.id)).scalar() or 0
            ticket_ref = f"MOCK-{count + 1}"

            # Ensure ticket_ref is strictly unique if multiple items created
            while session.query(TrackerTicket).filter(TrackerTicket.ticket_ref == ticket_ref).first():
                count += 1
                ticket_ref = f"MOCK-{count + 1}"

            ticket = TrackerTicket(
                ticket_ref=ticket_ref,
                title=title,
                body=body,
                assignee=assignee,
                due_date=due_date,
                labels=labels or ["decidr"],
                status="open",
                idempotency_key=idempotency_key,
                comments=[],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(ticket)
            if should_close:
                session.commit()
                session.refresh(ticket)
            else:
                session.flush()
            return {"ref": ticket.ticket_ref, "url": f"/mock-tracker#{ticket.ticket_ref}"}
        finally:
            if should_close:
                session.close()

    def add_comment(self, ref: str, text: str) -> None:
        session = self._get_session()
        should_close = self._db is None
        try:
            ticket = session.query(TrackerTicket).filter(TrackerTicket.ticket_ref == ref).first()
            if not ticket:
                raise ValueError(f"Ticket with ref '{ref}' not found in mock tracker")

            comments_list = list(ticket.comments or [])
            comments_list.append({
                "text": text,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            ticket.comments = comments_list
            ticket.updated_at = datetime.now(timezone.utc)
            if should_close:
                session.commit()
            else:
                session.flush()
        finally:
            if should_close:
                session.close()

    def reopen(self, ref: str) -> None:
        session = self._get_session()
        should_close = self._db is None
        try:
            ticket = session.query(TrackerTicket).filter(TrackerTicket.ticket_ref == ref).first()
            if not ticket:
                raise ValueError(f"Ticket with ref '{ref}' not found in mock tracker")
            ticket.status = "open"
            ticket.updated_at = datetime.now(timezone.utc)
            if should_close:
                session.commit()
            else:
                session.flush()
        finally:
            if should_close:
                session.close()

    def cancel(self, ref: str) -> None:
        session = self._get_session()
        should_close = self._db is None
        try:
            ticket = session.query(TrackerTicket).filter(TrackerTicket.ticket_ref == ref).first()
            if not ticket:
                raise ValueError(f"Ticket with ref '{ref}' not found in mock tracker")
            ticket.status = "cancelled"
            ticket.updated_at = datetime.now(timezone.utc)
            if should_close:
                session.commit()
            else:
                session.flush()
        finally:
            if should_close:
                session.close()
