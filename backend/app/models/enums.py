from enum import Enum


class MeetingStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    review = "review"
    done = "done"
    failed = "failed"


class ItemType(str, Enum):
    decision = "decision"
    action = "action"


class ReviewState(str, Enum):
    proposed = "proposed"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"


class DecisionStatus(str, Enum):
    active = "active"
    superseded = "superseded"
    at_risk = "at_risk"


class PremiseState(str, Enum):
    proposed = "proposed"
    confirmed = "confirmed"
    rejected = "rejected"


class PremiseStatus(str, Enum):
    holding = "holding"
    shaky = "shaky"
    broken = "broken"
    expired = "expired"


class LinkRelation(str, Enum):
    implements = "implements"
    depends_on = "depends_on"
    supersedes = "supersedes"


class TaskStatus(str, Enum):
    open = "open"
    at_risk = "at_risk"
    done = "done"
    cancelled = "cancelled"


class AlertKind(str, Enum):
    conflict = "conflict"
    premise_break = "premise_break"
    expiry = "expiry"


class AlertState(str, Enum):
    open = "open"
    confirmed = "confirmed"
    dismissed = "dismissed"


class ProposalState(str, Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    executed = "executed"


class ActionType(str, Enum):
    mark_decision_at_risk = "mark_decision_at_risk"
    comment_task = "comment_task"
    reopen_task = "reopen_task"
    create_task = "create_task"
    pause_reminders = "pause_reminders"
    cancel_task = "cancel_task"


class ActionState(str, Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    executed = "executed"
    failed = "failed"


class ReminderKind(str, Enum):
    three_day = "3d"
    one_day = "1d"
    morning = "morning"


class ReminderState(str, Enum):
    pending = "pending"
    sent = "sent"
    paused = "paused"
    skipped = "skipped"


class ReminderChannel(str, Enum):
    email = "email"
    slack = "slack"
