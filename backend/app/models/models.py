from datetime import date, datetime, timezone
from typing import Optional, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    Enum as SAEnum,
    event,
)
from sqlalchemy.orm import relationship, Session
from app.db.session import Base
from app.models.enums import (
    MeetingStatus,
    ItemType,
    ReviewState,
    DecisionStatus,
    PremiseState,
    PremiseStatus,
    LinkRelation,
    TaskStatus,
    AlertKind,
    AlertState,
    ProposalState,
    ActionType,
    ActionState,
    ReminderKind,
    ReminderState,
    ReminderChannel,
)


class ReadOnlyAuditLogError(Exception):
    """Raised when an attempt is made to update or delete an audit_log record."""
    pass


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    tracker_id = Column(String(255), nullable=False)
    slack_id = Column(String(255), nullable=True)

    utterances = relationship("Utterance", back_populates="person")
    items = relationship("Item", back_populates="owner")
    tasks = relationship("Task", back_populates="owner")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    project = Column(String(255), nullable=False, index=True)
    region = Column(String(100), nullable=True)
    release = Column(String(100), nullable=True)
    transcript_ref = Column(String(500), nullable=False)
    status = Column(
        SAEnum(MeetingStatus, name="meeting_status", native_enum=False),
        nullable=False,
        default=MeetingStatus.uploaded,
    )
    error = Column(String(1000), nullable=True)

    utterances = relationship("Utterance", back_populates="meeting", cascade="all, delete-orphan")
    items = relationship("Item", back_populates="meeting", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="meeting")


class Utterance(Base):
    __tablename__ = "utterances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    idx = Column(Integer, nullable=False)
    speaker_raw = Column(String(255), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True)
    text = Column(String(4000), nullable=False)
    start_ts = Column(Float, nullable=True)

    meeting = relationship("Meeting", back_populates="utterances")
    person = relationship("Person", back_populates="utterances")
    items = relationship("Item", back_populates="utterance")
    premises = relationship("Premise", back_populates="utterance")
    alerts = relationship("Alert", back_populates="utterance")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    type = Column(SAEnum(ItemType, name="item_type", native_enum=False), nullable=False)
    text = Column(String(2000), nullable=False)
    owner_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True)
    deadline = Column(Date, nullable=True)
    needs_owner = Column(Boolean, nullable=False, default=False)
    needs_deadline = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False, default=1.0)
    evidence_quote = Column(String(2000), nullable=False)
    utterance_id = Column(Integer, ForeignKey("utterances.id", ondelete="SET NULL"), nullable=True)
    review_state = Column(
        SAEnum(ReviewState, name="review_state", native_enum=False),
        nullable=False,
        default=ReviewState.proposed,
    )

    meeting = relationship("Meeting", back_populates="items")
    owner = relationship("Person", back_populates="items")
    utterance = relationship("Utterance", back_populates="items")
    decision = relationship("Decision", back_populates="item", uselist=False, cascade="all, delete-orphan")
    task = relationship("Task", back_populates="item", uselist=False, cascade="all, delete-orphan")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    text = Column(String(2000), nullable=False)
    scope_project = Column(String(255), nullable=False, index=True)
    scope_region = Column(String(100), nullable=True)
    scope_release = Column(String(100), nullable=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    status = Column(
        SAEnum(DecisionStatus, name="decision_status", native_enum=False),
        nullable=False,
        default=DecisionStatus.active,
    )
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(Integer, ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True)
    embedding = Column(String, nullable=True)

    item = relationship("Item", back_populates="decision")
    supersedes = relationship("Decision", remote_side=[id], backref="superseded_by")
    versions = relationship("DecisionVersion", back_populates="decision", cascade="all, delete-orphan")
    premises = relationship("Premise", back_populates="decision", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="decision")
    alerts = relationship("Alert", back_populates="decision")


class DecisionVersion(Base):
    __tablename__ = "decision_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(Integer, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    text = Column(String(2000), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    changed_by = Column(String(255), nullable=False)

    decision = relationship("Decision", back_populates="versions")


class Premise(Base):
    __tablename__ = "premises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(Integer, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False)
    text = Column(String(2000), nullable=False)
    evidence_quote = Column(String(2000), nullable=False)
    utterance_id = Column(Integer, ForeignKey("utterances.id", ondelete="SET NULL"), nullable=True)
    scope_project = Column(String(255), nullable=False, index=True)
    scope_region = Column(String(100), nullable=True)
    valid_from = Column(Date, nullable=True)
    valid_until = Column(Date, nullable=True)
    state = Column(
        SAEnum(PremiseState, name="premise_state", native_enum=False),
        nullable=False,
        default=PremiseState.proposed,
    )
    status = Column(
        SAEnum(PremiseStatus, name="premise_status", native_enum=False),
        nullable=False,
        default=PremiseStatus.holding,
    )
    confirmed_by = Column(String(255), nullable=True)
    last_supported_at = Column(DateTime(timezone=True), nullable=True)

    decision = relationship("Decision", back_populates="premises")
    utterance = relationship("Utterance", back_populates="premises")
    alerts = relationship("Alert", back_populates="premise")


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(50), nullable=False)
    source_id = Column(Integer, nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(Integer, nullable=False)
    relation = Column(
        SAEnum(LinkRelation, name="link_relation", native_enum=False),
        nullable=False,
    )
    confirmed = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False, default=1.0)
    rationale = Column(String(2000), nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    decision_id = Column(Integer, ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=True)
    owner_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(Date, nullable=True)
    estimate_hours = Column(Float, nullable=True)
    provisional = Column(Boolean, nullable=False, default=True)
    status = Column(
        SAEnum(TaskStatus, name="task_status", native_enum=False),
        nullable=False,
        default=TaskStatus.open,
    )
    tracker_ref = Column(String(255), nullable=True)
    tracker_url = Column(String(1000), nullable=True)

    item = relationship("Item", back_populates="task")
    decision = relationship("Decision", back_populates="tasks")
    owner = relationship("Person", back_populates="tasks")
    reminders = relationship("Reminder", back_populates="task", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(SAEnum(AlertKind, name="alert_kind", native_enum=False), nullable=False)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    utterance_id = Column(Integer, ForeignKey("utterances.id", ondelete="SET NULL"), nullable=True)
    premise_id = Column(Integer, ForeignKey("premises.id", ondelete="SET NULL"), nullable=True)
    decision_id = Column(Integer, ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True)
    verdict = Column(String(255), nullable=False)
    old_quote = Column(String(2000), nullable=True)
    new_quote = Column(String(2000), nullable=True)
    explanation = Column(String(2000), nullable=True)
    state = Column(
        SAEnum(AlertState, name="alert_state", native_enum=False),
        nullable=False,
        default=AlertState.open,
    )
    proposal_id = Column(Integer, ForeignKey("change_proposals.id", ondelete="SET NULL"), nullable=True)

    meeting = relationship("Meeting", back_populates="alerts")
    utterance = relationship("Utterance", back_populates="alerts")
    premise = relationship("Premise", back_populates="alerts")
    decision = relationship("Decision", back_populates="alerts")
    proposal = relationship("ChangeProposal", back_populates="alerts")


class ChangeProposal(Base):
    __tablename__ = "change_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_type = Column(String(50), nullable=False)
    trigger_id = Column(Integer, nullable=False)
    summary = Column(String(2000), nullable=False)
    state = Column(
        SAEnum(ProposalState, name="proposal_state", native_enum=False),
        nullable=False,
        default=ProposalState.draft,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    decided_by = Column(String(255), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    actions = relationship("ChangeAction", back_populates="proposal", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="proposal")


class ChangeAction(Base):
    __tablename__ = "change_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("change_proposals.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(SAEnum(ActionType, name="action_type", native_enum=False), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    state = Column(
        SAEnum(ActionState, name="action_state", native_enum=False),
        nullable=False,
        default=ActionState.draft,
    )
    executed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSON, nullable=True)

    proposal = relationship("ChangeProposal", back_populates="actions")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    kind = Column(SAEnum(ReminderKind, name="reminder_kind", native_enum=False), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False)
    state = Column(
        SAEnum(ReminderState, name="reminder_state", native_enum=False),
        nullable=False,
        default=ReminderState.pending,
    )
    channel = Column(
        SAEnum(ReminderChannel, name="reminder_channel", native_enum=False),
        nullable=False,
        default=ReminderChannel.email,
    )
    pause_reason = Column(String(500), nullable=True)

    task = relationship("Task", back_populates="reminders")


class Outbox(Base):
    __tablename__ = "outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(50), nullable=False)
    to_addr = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=True)
    body = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    sent = Column(Boolean, nullable=False, default=False)


class TrackerTicket(Base):
    __tablename__ = "tracker_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_ref = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=True)
    assignee = Column(String(255), nullable=True)
    due_date = Column(String(50), nullable=True)
    labels = Column(JSON, nullable=False, default=list)
    status = Column(String(50), nullable=False, default="open")
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    comments = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=False)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


# Append-only enforcement on AuditLog
@event.listens_for(AuditLog, "before_update")
def audit_log_before_update(mapper, connection, target):
    raise ReadOnlyAuditLogError("audit_log is append-only: updates are prohibited")


@event.listens_for(AuditLog, "before_delete")
def audit_log_before_delete(mapper, connection, target):
    raise ReadOnlyAuditLogError("audit_log is append-only: deletions are prohibited")


@event.listens_for(Session, "before_flush")
def prevent_audit_log_flush_mutations(session, flush_context, instances):
    for obj in session.dirty:
        if isinstance(obj, AuditLog):
            raise ReadOnlyAuditLogError("audit_log is append-only: updates are prohibited")
    for obj in session.deleted:
        if isinstance(obj, AuditLog):
            raise ReadOnlyAuditLogError("audit_log is append-only: deletions are prohibited")


@event.listens_for(Session, "do_orm_execute")
def check_bulk_audit_log_execution(orm_execute_state):
    if orm_execute_state.is_update or orm_execute_state.is_delete:
        for mapper in orm_execute_state.all_mappers:
            if issubclass(mapper.class_, AuditLog):
                raise ReadOnlyAuditLogError("audit_log is append-only: bulk updates and deletes are prohibited")
