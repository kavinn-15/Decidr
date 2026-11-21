# DECIDR — Requirements Traceability Matrix (RTM)

This matrix maps every requirement from the authoritative product specification (`Decidr_Final_Problem_Statement_v2.docx`) and system invariants (`AGENTS.md`) to its backend implementation, database entities, API endpoints, frontend views, and verification tests.

---

## 1. Core Platform Requirements Traceability

| Ref # | Feature / Specification | Backend Module | Database Model / Table | API Endpoints | Frontend View | Verification Test(s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-01** | **Transcript Ingestion & Normalization**: Support WebVTT, SRT, TXT, JSON; parse utterances with timestamps. | `app/services/ingestion.py` | `Meeting`, `Utterance` | `POST /meetings`<br>`GET /meetings`<br>`GET /meetings/{id}/utterances` | `/` (Upload modal & Meeting List) | `test_ingestion.py`<br>`test_adversarial.py` |
| **REQ-02** | **Speaker Roster Resolution**: Exact/fuzzy matching; flag unmapped speakers without guessing. | `app/services/ingestion.py` | `Person`, `Utterance.person_id` | `GET /meetings/roster/people`<br>`PATCH /meetings/{id}/speakers` | `/` (Unmapped Speaker dialog) | `test_ingestion.py::test_unmapped_speaker_matching` |
| **REQ-03** | **Two-Pass Extraction**: Pass 1 extracts decisions, actions, premises with verbatim quotes; Pass 2 links them. | `app/services/extraction.py` | `Item`, `Decision`, `Premise`, `Task`, `Link` | `POST /meetings/{id}/process`<br>`GET /review/items` | `/review` (Proposed Items) | `test_extraction.py` |
| **REQ-04** | **Missing Owner & Deadline Flagging (Inv 1)**: Null fields flagged with `needs_owner=True`, `needs_deadline=True`. | `app/services/extraction.py` | `Item.needs_owner`<br>`Item.needs_deadline` | `GET /review/items`<br>`POST /review/items/{id}/approve` | `/review` (Item Cards) | `test_extraction.py::test_missing_owner_and_deadline_flagged` |
| **REQ-05** | **Relative Date Resolution (Inv 8)**: "next Friday" resolved relative to meeting date into ISO format. | `app/services/extraction.py` | `Task.due_date` | `POST /meetings/{id}/process` | `/review`<br>`/ledger` | `test_extraction.py::test_relative_date_resolution` |
| **REQ-06** | **Decision Scope & Explicit Time (Inv 9)**: Decisions and premises carry `project`, `region`, `release`, and effective dates. | `app/services/ledger.py` | `Decision.scope_*`<br>`Premise.scope_*` | `GET /decisions`<br>`GET /ledger/search` | `/ledger` | `test_ledger_links.py`<br>`test_false_positives.py` |
| **REQ-07** | **Continuous Premise Watchdog**: Scans every 5+ word utterance; BM25 candidate selection; batched LLM judge. | `app/services/premise_watch.py` | `Premise.status`<br>`Premise.last_supported_at` | `POST /alerts/watch`<br>`GET /alerts` | `/review` (Alert Cards) | `test_premise_watch.py`<br>`test_false_positives.py` |
| **REQ-08** | **Premise Expiry Management**: Calendar-based expiry without needing a new meeting; shaky window within 7 days. | `app/services/premise_watch.py` | `Premise.valid_until`<br>`Premise.status` | `POST /admin/run-expiry`<br>`GET /alerts` | `/review`<br>`/ledger` | `test_premise_watch.py::test_m4_sandbox_premise_expires` |
| **REQ-09** | **Deterministic Blast Radius (Inv 4 & 5)**: Walk confirmed links only; cycle-safe; exact causal chains; zero LLM. | `app/services/blast_radius.py` | `Link.confirmed`<br>`Decision`, `Task` | `GET /alerts/{id}/blast-radius`<br>`GET /blast-radius/premise/{id}` | `/affected` (Interactive Graph & Table) | `test_blast_radius.py` |
| **REQ-10** | **Hours at Risk Calculation (Inv 10)**: Sum of measured open task hours; count of unestimated tasks; no guessing. | `app/services/blast_radius.py` | `Task.estimate_hours` | `GET /alerts/{id}/blast-radius` | `/affected` (Metric Badges) | `test_blast_radius.py::test_hours_at_risk_unestimated_count` |
| **REQ-11** | **Human-in-the-Loop Repair Engine**: Generate rule-based draft repair proposals; human approves, edits, or rejects. | `app/services/repair.py` | `ChangeProposal`<br>`ChangeAction` | `GET /proposals/{id}`<br>`POST /proposals/{id}/approve`<br>`POST /proposals/{id}/reject` | `/review` (Repair Modal) | `test_repair.py` |
| **REQ-12** | **External Action Execution (Inv 2 & 3)**: Dispatches approved actions; enforced by SHA-256 idempotency key. | `app/services/executor.py` | `TrackerTicket`<br>`ChangeAction.idempotency_key` | `POST /proposals/{id}/execute` | `/review`<br>`/my-week` | `test_executor.py` |
| **REQ-13** | **Scheduled Reminders & Weekly Digest**: 3d/1d/morning-of alerts; shaky premise warnings; outbox table. | `app/services/reminders.py`<br>`app/services/digest.py` | `Reminder`, `OutboxMessage` | `GET /digest/{person_id}`<br>`POST /admin/run-reminders` | `/my-week` | `test_reminders_digest.py` |
| **REQ-14** | **Searchable Decision Ledger & Detail Drawer**: Text search, faceted filters, timeline from audit, premise chips. | `app/services/ledger.py` | `Decision`, `DecisionVersion`, `Premise` | `GET /decisions`<br>`GET /decisions/{id}`<br>`GET /decisions/{id}/history` | `/ledger` (Search Table & Drawer) | `test_ledger_links.py` |
| **REQ-15** | **Append-Only Audit Log (Inv 7)**: Records actor, entity, before/after JSON diffs, timestamps. Search and export. | `app/services/audit.py` | `AuditLog` | `GET /audit`<br>`GET /audit/export` | `/audit` (Table & Export) | `test_audit_api.py` |
| **REQ-16** | **Pipeline Evaluation & Baseline Comparison**: Measures P/R against gold labels for Decidr, B1, and B2. | `backend/eval/run_eval.py` | Gold labels (`gold_labels.json`) | `GET /eval/report`<br>`POST /eval/run` | `/eval` | `test_eval.py` |
| **REQ-17** | **Right-to-be-Forgotten & Privacy**: Purges transcript and derived items; preserves non-content audit row. | `app/api/routes/meetings.py` | All tables (`Meeting`, `Item`, etc.) | `DELETE /meetings/{id}` | `/` (Delete Meeting) | `test_adversarial.py` |
| **REQ-18** | **Adversarial & Injection Hardening**: Prompt injection treated as passive text; path traversal stripped. | Ingestion, Routes, Executor | `Utterance`, `Meeting` | `POST /meetings` | `/` | `test_adversarial.py` |

---

## 2. Invariants Traceability (AGENTS.md)

| Invariant # | Formulation | Primary Enforcement Code | Primary Test Case |
| :--- | :--- | :--- | :--- |
| **1** | Never guess an owner or deadline. If missing, store `null` and set `needs_owner=True` or `needs_deadline=True`. | `backend/app/services/extraction.py` (lines 142–165) | `backend/tests/test_extraction.py::test_missing_owner_and_deadline_flagged` |
| **2** | Never write to an external system unless approved (`change_proposal` state must be `approved`). | `backend/app/services/executor.py` (lines 45–62) | `backend/tests/test_executor.py::test_unapproved_proposal_creates_zero_external_writes` |
| **3** | Execution is idempotent: `idempotency_key = sha256(alert_id:action_type:target_id)`. | `backend/app/services/executor.py` (lines 68–85) | `backend/tests/test_executor.py::test_idempotent_execution_does_not_duplicate_writes` |
| **4** | Unconfirmed premises and unconfirmed links are never treated as fact. | `backend/app/services/premise_watch.py` & `blast_radius.py` | `backend/tests/test_premise_watch.py::test_unconfirmed_premise_is_never_checked` |
| **5** | The LLM only PROPOSES. Plain application code handles traversal, checks, approvals, deduplication. | `backend/app/services/blast_radius.py` & `repair.py` | `backend/tests/test_blast_radius.py::test_blast_radius_traversal_pure_code_zero_llm` |
| **6** | Every LLM output is validated against Pydantic schema and exact substring quotes. | `backend/app/services/extraction.py` & `premise_watch.py` | `backend/tests/test_adversarial.py::test_fabricated_llm_quote_is_dropped` |
| **7** | Every state change writes an `audit_log` row with actor, action, item, timestamp, before/after states. | `backend/app/services/audit.py` (lines 18–48) | `backend/tests/test_audit_api.py::test_audit_log_append_only_and_search` |
| **8** | Relative dates are resolved against meeting date into ISO format (`YYYY-MM-DD`). | `backend/app/services/extraction.py` (lines 102–130) | `backend/tests/test_extraction.py::test_relative_date_resolution` |
| **9** | Scope and time are explicit (`project`, `region`, `release`). Disjoint scopes raise no alerts. | `backend/app/services/ledger.py` (`scope_overlap`) | `backend/tests/test_false_positives.py::test_case_a_same_vendor_different_country` |
| **10** | Report only measured numbers: Never hard-code, guess, or invent metrics. | `backend/eval/run_eval.py` & `blast_radius.py` | `backend/tests/test_eval.py::test_eval_metrics_strictly_measured` |
