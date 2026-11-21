from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field
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


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- People ---
class PersonBase(BaseSchema):
    name: str
    email: str
    tracker_id: str
    slack_id: Optional[str] = None


class PersonCreate(PersonBase):
    pass


class PersonRead(PersonBase):
    id: int


# --- Meetings ---
class MeetingBase(BaseSchema):
    title: str
    date: date
    project: str
    region: Optional[str] = None
    release: Optional[str] = None
    transcript_ref: str
    status: MeetingStatus = MeetingStatus.uploaded
    error: Optional[str] = None


class MeetingCreate(MeetingBase):
    pass


class MeetingRead(MeetingBase):
    id: int


# --- Utterances ---
class UtteranceBase(BaseSchema):
    meeting_id: int
    idx: int
    speaker_raw: str
    person_id: Optional[int] = None
    text: str
    start_ts: Optional[float] = None


class UtteranceCreate(UtteranceBase):
    pass


class UtteranceRead(UtteranceBase):
    id: int


# --- Items ---
class ItemBase(BaseSchema):
    meeting_id: int
    type: ItemType
    text: str
    owner_id: Optional[int] = None
    deadline: Optional[date] = None
    needs_owner: bool = False
    needs_deadline: bool = False
    confidence: float = 1.0
    evidence_quote: str
    utterance_id: Optional[int] = None
    review_state: ReviewState = ReviewState.proposed


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: int


# --- Decisions ---
class DecisionBase(BaseSchema):
    item_id: int
    text: str
    scope_project: str
    scope_region: Optional[str] = None
    scope_release: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    status: DecisionStatus = DecisionStatus.active
    version: int = 1
    supersedes_id: Optional[int] = None
    embedding: Optional[str] = None


class DecisionCreate(DecisionBase):
    pass


class DecisionRead(DecisionBase):
    id: int


# --- Decision Versions ---
class DecisionVersionBase(BaseSchema):
    decision_id: int
    version: int
    text: str
    changed_at: datetime
    changed_by: str


class DecisionVersionCreate(DecisionVersionBase):
    pass


class DecisionVersionRead(DecisionVersionBase):
    id: int


# --- Premises ---
class PremiseBase(BaseSchema):
    decision_id: int
    text: str
    evidence_quote: str
    utterance_id: Optional[int] = None
    scope_project: str
    scope_region: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    state: PremiseState = PremiseState.proposed
    status: PremiseStatus = PremiseStatus.holding
    confirmed_by: Optional[str] = None


class PremiseCreate(PremiseBase):
    pass


class PremiseRead(PremiseBase):
    id: int


# --- Links ---
class LinkBase(BaseSchema):
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    relation: LinkRelation
    confirmed: bool = False
    confidence: float = 1.0
    rationale: Optional[str] = None


class LinkCreate(LinkBase):
    pass


class LinkRead(LinkBase):
    id: int


# --- Tasks ---
class TaskBase(BaseSchema):
    item_id: int
    decision_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    owner_id: Optional[int] = None
    due_date: Optional[date] = None
    estimate_hours: Optional[float] = None
    provisional: bool = True
    status: TaskStatus = TaskStatus.open
    tracker_ref: Optional[str] = None
    tracker_url: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    id: int


# --- Alerts ---
class AlertBase(BaseSchema):
    kind: AlertKind
    meeting_id: Optional[int] = None
    utterance_id: Optional[int] = None
    premise_id: Optional[int] = None
    decision_id: Optional[int] = None
    verdict: str
    old_quote: Optional[str] = None
    new_quote: Optional[str] = None
    explanation: Optional[str] = None
    state: AlertState = AlertState.open
    proposal_id: Optional[int] = None


class AlertCreate(AlertBase):
    pass


class AlertRead(AlertBase):
    id: int


# --- Change Proposals ---
class ChangeProposalBase(BaseSchema):
    trigger_type: str
    trigger_id: int
    summary: str
    state: ProposalState = ProposalState.draft
    created_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None


class ChangeProposalCreate(BaseSchema):
    trigger_type: str
    trigger_id: int
    summary: str
    state: ProposalState = ProposalState.draft


class ChangeProposalRead(ChangeProposalBase):
    id: int


# --- Change Actions ---
class ChangeActionBase(BaseSchema):
    proposal_id: int
    action_type: ActionType
    target_type: str
    target_id: int
    payload: dict[str, Any]
    idempotency_key: str
    state: ActionState = ActionState.draft
    executed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None


class ChangeActionCreate(BaseSchema):
    proposal_id: int
    action_type: ActionType
    target_type: str
    target_id: int
    payload: dict[str, Any]
    idempotency_key: str
    state: ActionState = ActionState.draft


class ChangeActionRead(ChangeActionBase):
    id: int


# --- Reminders ---
class ReminderBase(BaseSchema):
    task_id: int
    kind: ReminderKind
    due_at: datetime
    state: ReminderState = ReminderState.pending
    channel: ReminderChannel = ReminderChannel.email
    pause_reason: Optional[str] = None


class ReminderCreate(ReminderBase):
    pass


class ReminderRead(ReminderBase):
    id: int


# --- Outbox ---
class OutboxBase(BaseSchema):
    channel: str
    to_addr: str
    subject: Optional[str] = None
    body: str
    sent: bool = False


class OutboxCreate(OutboxBase):
    pass


class OutboxRead(OutboxBase):
    id: int
    created_at: datetime


# --- Audit Log ---
class AuditLogBase(BaseSchema):
    actor: str
    action: str
    entity_type: str
    entity_id: int
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    id: int
    created_at: datetime
