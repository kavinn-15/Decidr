# Decidr - System Invariants & Operating Guidelines

These 10 invariants govern all agent behavior and system operations in Decidr:

1. **Never guess an owner or deadline**: If missing from the transcript or context, store `null` and explicitly flag the item with `needs_owner=True` or `needs_deadline=True`.
2. **Never write to an external system (tracker, email, Slack) unless approved**: A `change_proposal` row must be in state `approved`. Rejected or draft proposals cause zero external calls.
3. **Execution is idempotent**: Every external action carries a unique `idempotency_key = sha256(alert_id:action_type:target_id)`. Running an execution twice creates nothing new.
4. **Unconfirmed premises and unconfirmed links are never treated as fact**: Detection and blast-radius logic ignore unconfirmed premises and provisional links by default.
5. **The LLM only PROPOSES**: Plain application code does graph traversal, missing-field checks, approval-state enforcement, and duplicate prevention.
6. **Every LLM output is validated against Pydantic schema and exact substring quotes**: Every `evidence_quote` must be an exact substring of the transcript; if not, discard the item and log it.
7. **Every state change writes an audit_log row**: Records actor, action, item, timestamp, before/after states, and result payload. Audit log is append-only.
8. **Relative dates are resolved against meeting date**: Statements like "next Friday" or "by Nov 20" are resolved using the meeting date and stored as ISO dates (`YYYY-MM-DD`).
9. **Scope and time are explicit**: `project`, `region`, `release`, and effective dates are compared. Decisions with disjoint scope (e.g., India vs. Europe) must NOT raise conflict or premise-break alerts.
10. **Report only measured numbers**: Never hard-code, guess, or invent metrics.
