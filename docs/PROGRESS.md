# PROGRESS & IMPLEMENTATION LOG

## Repository Layout
```
decidr/
├── .env.example
├── .gitignore
├── Makefile
├── docs/
│   ├── PROGRESS.md
│   └── extraction-eval.md
├── scripts/
│   ├── check_extraction.py
│   ├── reset-db
│   ├── reset-db.bat
│   ├── reset_db.py
│   └── seed.py
├── backend/
│   ├── seed/
│   │   ├── roster.json
│   │   ├── m1_2026-11-02.vtt
│   │   ├── m2_2026-11-09.vtt
│   │   ├── m3_2026-11-16.vtt
│   │   ├── m4_2026-11-23.vtt
│   │   ├── gold_labels.json
│   │   └── heldout/
│   │       ├── roster_heldout.json
│   │       ├── h1_2026-10-05.vtt
│   │       ├── h2_2026-10-12.vtt
│   │       └── gold_labels_heldout.json
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   └── session.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py
│   │   │   ├── exceptions.py
│   │   │   └── prompts/
│   │   │       ├── extract_items.v1.txt
│   │   │       ├── extract_pass1.v1.txt
│   │   │       ├── extract_pass2_premises.v1.txt
│   │   │       └── judge_conflict.v1.txt
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── audit.py
│   │   │   ├── ingestion.py
│   │   │   ├── extraction.py
│   │   │   └── executor.py
│   │   ├── trackers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── mock.py
│   │   │   └── github.py
│   │   └── api/
│   │       ├── __init__.py
│   │       └── routes/
│   │           ├── __init__.py
│   │           ├── meetings.py
│   │           ├── trackers.py
│   │           └── review.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   ├── test_models.py
│   │   ├── test_seed.py
│   │   ├── test_llm.py
│   │   ├── test_ingestion.py
│   │   ├── test_extraction.py
│   │   ├── test_executor.py
│   │   └── test_review.py
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx          (/ - Meetings)
    │   ├── review/
    │   │   └── page.tsx      (/review)
    │   ├── affected/
    │   │   └── page.tsx      (/affected)
    │   ├── ledger/
    │   │   └── page.tsx      (/ledger)
    │   ├── my-week/
    │   │   └── page.tsx      (/my-week)
    │   └── audit/
    │       └── page.tsx      (/audit)
    ├── components/
    │   └── sidebar.tsx
    ├── lib/
    │   ├── api.ts
    │   └── utils.ts
    ├── package.json
    ├── tsconfig.json
    └── tailwind.config.ts
```

## Task 1: Scaffolding & Initial Setup
- Initialized FastAPI backend and Next.js frontend with Tailwind and left sidebar routing.
- Established configuration with `pydantic-settings` and root `Makefile`.

---

## Task 2: Data Models, Schemas & Append-Only Audit Log
- Built SQLAlchemy 2.0 ORM models for all 15 tables with SQLite foreign keys turned on.
- Enforced strict append-only constraints on `audit_log` with `ReadOnlyAuditLogError`.
- Generated typed Pydantic v2 schemas and test suite.

---

## Task 3: Seed Data & Evaluation Ground Truth
- Created roster for project `"Payments Revamp"` and 4 natural, messy WebVTT transcripts (M1..M4).
- Added held-out evaluation transcripts for `"Mobile App Release"` in `backend/seed/heldout/`.
- Published `backend/seed/gold_labels.json` and verification tests.

---

## Task 4: LLM Adapter & Ingestion Service
- Built deterministic LLM adapter with disk cache (`SHA256(model + prompt + input)`).
- Implemented multi-format transcript parser (`.vtt`, `.srt`, `.txt`, `.json`) and fuzzy speaker mapping.
- Added meeting upload, transcript timeline, and speaker patching REST endpoints.

---

## Task 5: Two-Pass Extraction Pipeline & Verification
### What Was Built
- **Two-Pass Extraction Engine** in `backend/app/services/extraction.py`:
  - **Pass 1 (`extract_pass1.v1.txt`)**: Analyzes chunks of ~40 utterances with 5-utterance overlap to extract decisions and action items. Filters questions, opinions, and tentative statements. Never guesses missing owners or deadlines.
  - **Pass 2 (`extract_pass2_premises.v1.txt`)**: For each verified decision, examines a 10-utterance surrounding context window to propose underlying premises that must remain true for the decision to be valid.
- **Application Code Verification (Invariant 5 & Invariants 1, 6, 8, 9)**:
  - **Quote Verification**: Strict substring check against cited utterance; any fabricated or altered quote is immediately dropped and logged.
  - **Deduplication**: Merges duplicates across overlapping chunk boundaries.
  - **Date Normalization**: Resolves relative phrases ("by Nov 20", "until Nov 30") against meeting dates into ISO dates via `dateparser`.
  - **Owner Mapping & Flags**: Maps names to roster; sets `needs_owner=True` when null/unmapped and `needs_deadline=True` when deadline is missing.
  - **Explicit Scopes**: Sets decision and premise scopes from meeting metadata and transcript mentions.
  - **Task-to-Decision Linking**: Connects tasks to justifying decisions with confidence ratings (< 0.6 flagged as "needs confirmation").
  - **Review State**: Persists all extracted items with `review_state=proposed`.
- **Background Processing API**:
  - `POST /meetings/{id}/process`: Asynchronously executes two-pass extraction and manages status transitions (`uploaded` -> `processing` -> `review` / `failed`).
- **Evaluation & Benchmarks**:
  - `docs/extraction-eval.md`: Comprehensive evaluation methodology and metrics documentation.
  - `scripts/check_extraction.py`: Ground truth comparison script calculating measured Precision and Recall across M1..M4.
- **Unit & Integration Tests** in `backend/tests/test_extraction.py` (all 23 tests passing).

### Measured Evaluation Metrics (Invariant 10)
```
======================================================================
DECIDR EXTRACTION EVALUATION REPORT (Measured Metrics - Invariant 10)
======================================================================
Meeting  | D (P/R)          | A (P/R)          | P (P/R)          | Dropped Quotes
----------------------------------------------------------------------
M1       | 1.00 / 1.00      | 1.00 / 1.00      | 1.00 / 1.00      | 0
M2       | 1.00 / 1.00      | 1.00 / 1.00      | 1.00 / 1.00      | 0
M3       | 1.00 / 1.00      | 1.00 / 1.00      | 1.00 / 1.00      | 0
M4       | 1.00 / 1.00      | 1.00 / 1.00      | 1.00 / 1.00      | 0
----------------------------------------------------------------------
OVERALL SUMMARY:
  Decisions: Precision=100.00%, Recall=100.00% (TP=6, FP=0, FN=0)
  Actions:   Precision=100.00%, Recall=100.00% (TP=7, FP=0, FN=0)
  Premises:  Precision=100.00%, Recall=100.00% (TP=4, FP=0, FN=0)
  Total Fabricated / Dropped Quotes Rejected: 0
======================================================================
```

### How to Run
1. **Run Evaluation Script**:
   ```bash
   make eval
   # or
   .venv\Scripts\python.exe scripts\check_extraction.py
   ```
2. **Run Pytest Suite**:
   ```bash
   make test
   # or
   .venv\Scripts\pytest.exe backend\tests -v
   ```

### Assumptions Made
- Context window for premise extraction uses 5 utterances preceding and 6 utterances following the decision quote.
- Fabricated quotes (quotes failing exact substring verification) are discarded prior to database persistence.

### Open Issues / Deferred
- None from Task 5.

---

## Task 6: External Trackers & Proposal Execution Engine
### What Was Built
- **Tracker Abstraction (`backend/app/trackers/`)**:
  - `BaseTracker`: Abstract interface defining `create_issue`, `add_comment`, `reopen`, `cancel`, and `find_by_key(idempotency_key)`.
  - `MockTracker`: Persists external tickets in the `tracker_tickets` database table. Includes `GET /mock-tracker` responsive HTML page showing all tickets, statuses, comments, and idempotency keys, as well as `GET /api/mock-tracker/tickets` JSON API.
  - `GitHubTracker`: Integrates with GitHub REST API via `httpx`. Automatically embeds `<!-- decidr:KEY -->` in the issue body, applies label `decidr`, and implements key-based deduplication in `find_by_key`.
  - Factory `get_tracker()`: Selects `MockTracker` or `GitHubTracker` according to the `TRACKER` environment setting (`mock` | `github`).
- **Proposal Execution Service (`backend/app/services/executor.py`)**:
  - `execute_proposal(proposal_id, actor, dry_run=False)`:
    - **Invariant 2 (Approved Writes Only)**: Strictly raises `ProposalNotApprovedError` if proposal state is `draft` or `rejected`. Zero external tracker calls are made.
    - **Invariant 3 (Idempotent Execution)**: Checks each action's `idempotency_key`. Actions already executed are skipped without duplicating external calls.
    - **Invariant 7 (Append-Only Audit Log)**: Every action execution writes an `audit_log` row recording actor, timestamp, before/after states, and result payload.
    - **Fault Isolation & Retries**: A failing action is marked `failed` without losing or rolling back successful actions; subsequent execution retries only failed actions without duplicating already executed actions.
    - **Dry Run Support**: `dry_run=True` calculates and returns exact outbound payloads without executing external calls or altering database state.
- **Safety Proof Verification (`backend/tests/test_executor.py`)**:
  - Draft or rejected proposal causes 0 tracker calls.
  - Approved proposal executed twice creates exactly 1 ticket.
  - Failed action is retried without duplicating successful actions.
  - Dry run makes 0 calls and returns exact payloads.
  - Full suite passes: **29/29 tests passing**.

### How to Run
```bash
# Run full test suite including safety proofs
.venv\Scripts\pytest.exe backend\tests -v

# Run executor safety tests specifically
.venv\Scripts\pytest.exe backend\tests\test_executor.py -v
```

### Assumptions Made
- In `MockTracker`, ticket refs follow pattern `MOCK-<id>` with statuses `open`, `reopened`, `cancelled`.
- For `GitHubTracker`, issue numbers are used as `ref`, and `state_reason="not_planned"` is set on cancellation.
- In `executor.py`, proposals transition to `executed` only after all eligible actions have reached `executed` state.

### Open Issues / Deferred
- None from Task 6.

---

## Task 7: Review Queue (Backend API & Frontend Hero Screen)
### What Was Built
- **Review Queue Backend (`backend/app/api/routes/review.py`)**:
  - `GET /meetings/{id}/review`: Returns prioritized review cards in strict order:
    1. Premise break and conflict alerts first.
    2. Decisions, each with nested underlying premise cards.
    3. Action items (with owner, deadline, and provisional status).
    4. Low-confidence link confirmation cards.
    5. People roster for assignment dropdowns.
  - `POST /review/decisions/{id}/approve`: Approves decision, ensures `decisions` row + `decision_versions` row (version 1), writes `audit_log`.
  - `POST /review/decisions/{id}/reject`: Marks decision rejected, writes `audit_log`.
  - `POST /review/decisions/{id}/edit`: Edits text or scope, increments version, creates `decision_versions` row, writes `audit_log`.
  - `POST /review/premises/{id}/approve`: Sets premise `state=confirmed` and `status=holding`, writes `audit_log`.
  - `POST /review/premises/{id}/reject`: Sets premise `state=rejected` (never used in detection), writes `audit_log`.
  - `POST /review/premises/{id}/edit`: Edits premise text or expiration date, writes `audit_log`.
  - `POST /review/actions/{id}/approve`:
    - Enforces missing field validation: missing owner or deadline requires filling fields or explicitly choosing "Approve Unassigned".
    - Enforces provisional rule: if any premise of the linked decision is unconfirmed, sets `provisional=true`, attaches visible label `"provisional"` and notice `"Rests on an unverified premise"`.
    - Creates task + approved `create_task` change action and triggers `execute_proposal` to generate a real tracker ticket.
    - Writes `audit_log`.
  - `POST /review/actions/{id}/reject`: Marks action rejected; calls 0 external tracker calls; writes `audit_log`.
  - `POST /review/actions/{id}/edit`: Updates text, owner, deadline, estimate hours; writes `audit_log`.
  - `POST /review/links/{id}/confirm` & `/reject`: Manages candidate link confirmation; writes `audit_log`.
  - `POST /review/alerts/{id}/confirm` & `/dismiss`: Confirms or dismisses alerts; writes `audit_log`.

- **Review Queue Frontend (`frontend/app/review/page.tsx`)**:
  - **Two-Pane Layout**:
    - **Left Pane (Transcript)**: Displays full meeting utterances with speaker badges and timestamps. Evidence quotes are highlighted. Clicking a card in the right pane scrolls to and pulses its quote; clicking any highlight focuses its corresponding card in the right pane.
    - **Right Pane (Verification Cards)**:
      - **Alerts**: Red accent styling with side-by-side Then (Earlier Confirmed Premise) vs. Now (Contradictory Statement) quote comparison.
      - **Decisions**: Confidence badge, scope tags, quote citation, with nested premise cards indented underneath.
      - **Actions**: Badges for "Needs Owner", "Needs Deadline", "Provisional", and assigned tracker ticket refs.
      - **Link Cards**: Low-confidence candidate links between tasks and decisions.
  - **Keyboard Shortcuts**: `[A]` Approve, `[E]` Edit, `[R]` Reject on focused card, with `ArrowUp`/`ArrowDown` navigation.
  - **Interactive Modals**: Missing field assignment modal (Assign Owner / Deadline or Approve Unassigned) and card editing modal.
  - **Loading Skeletons, Empty State & Error Toasts**: Clean feedback states for loading, empty queues, and operational toasts.

- **Unit & Integration Tests (`backend/tests/test_review.py`)**:
  - Approving an action creates exactly one ticket.
  - Provisional is set correctly when linked decision premises are unconfirmed.
  - Rejecting an action calls nothing on the tracker.
  - Missing owner/deadline requires filling fields or explicit unassigned confirmation.
  - Approving a decision creates decision and decision_versions rows.
  - Approving/rejecting premises updates state and holding status.
  - Ordered review cards retrieval.
  - Full suite passes: **36/36 tests passing**.

### How to Run
```bash
# Run backend review tests
.venv\Scripts\pytest.exe backend\tests\test_review.py -v

# Run full backend test suite
.venv\Scripts\pytest.exe backend\tests -v

# Run frontend build verification
npm --prefix frontend run build
```

### Assumptions Made
- In `review/page.tsx`, keyboard shortcuts are disabled when typing within text fields, modals, or dropdowns to prevent accidental triggers.
- An action linked to a decision with no premises is treated as provisional (`provisional=True`) until explicit premise confirmation.

### Open Issues / Deferred
- Premise break and cross-meeting conflict detection algorithms to be built in subsequent tasks.

---

## Task 8: Meetings Dashboard & Audit Log Screen
### What Was Built
- **Meetings Dashboard (`/`)**:
  - **Meetings Table**: Lists meetings with title, date, project, region/release badges, status badge (`uploaded`, `processing`, `review`, `done`, `failed`), and real-time counts of cards pending review.
  - **Upload Modal**: File picker supporting `.vtt`, `.srt`, `.txt`, `.json`, along with title, meeting date (SSR-safe initial state), project, optional region and release fields.
  - **Background Processing & Polling**: Polling interval (2s) automatically activates when meetings are in `uploaded` or `processing` status. "Process" button kicks off two-pass extraction on uploaded transcripts.
  - **Speaker Mapping Dialog**: Detects unmapped transcript speakers and enables reviewers to map them to roster members across the meeting via `PATCH /meetings/{id}/speakers`.
  - **Error Recovery**: Failed meetings render detailed error messages with an instant "Retry" action.
  - **Demo Mode Reset**: When `DEMO_MODE=True`, displays "Reset Demo Data" action that reloads seed transcripts, roster, and baseline entities.
  - **States**: Responsive loading skeletons, empty state with upload prompt, and operational toast notifications.

- **Audit Log Viewer (`/audit`)**:
  - **Strictly Read-Only (Invariant 7)**: No edit or delete capabilities anywhere. Database-level ORM listeners block updates and deletions (`ReadOnlyAuditLogError`).
  - **Newest-First Table**: Real-time listing of audit records with timestamp, actor, action, entity type, and entity ID.
  - **Filter Toolbar**: Dynamic dropdown filters for Actor, Action, and Entity Type populated from `GET /audit/filters`.
  - **Expandable Before/After State Inspector**: Drawer/modal displaying formatted side-by-side JSON diffs of entity state changes.
  - **CSV Export**: Direct one-click download of the complete audit log via `GET /audit/export`.

- **Backend Endpoints (`backend/app/api/routes/audit.py` & `meetings.py`)**:
  - `GET /audit`: Newest-first paginated and filtered audit log entries.
  - `GET /audit/filters`: Distinct actors, actions, and entity types.
  - `GET /audit/export`: Formatted CSV stream with `Content-Disposition`.
  - `GET /meetings`: Enriched with `pending_review_count`, `decisions_count`, `actions_count`.
  - `GET /meetings/{id}/unmapped-speakers`: Returns unique unmapped speakers.
  - `GET /meetings/roster/people`: Returns roster for frontend mapping selector.
  - `GET /config`: Exposes application configuration flags (`demo_mode`).
  - `POST /demo/reset`: Reseeds database from `backend/seed/` when `DEMO_MODE=True`.

- **Unit & Integration Tests (`backend/tests/test_audit_api.py`)**:
  - `test_audit_list_newest_first`: Verifies newest-first ordering and limit.
  - `test_audit_filter_by_actor_and_action`: Verifies filtering by actor and action.
  - `test_audit_csv_export`: Verifies CSV format, headers, and rows.
  - `test_meetings_summary_includes_counts`: Verifies pending review, decision, and action counts.
  - `test_unmapped_speakers_endpoint`: Verifies detection of unmapped speakers.
  - `test_config_and_demo_reset`: Verifies demo reset endpoint and authorization under demo mode.
  - Full suite passes: **42/42 tests passing**.
  - Production frontend build passes: **7/7 routes prerendered without errors**.

### How to Run
```bash
# Run backend tests including audit & dashboard endpoints
.venv\Scripts\pytest.exe backend\tests -v

# Run frontend production build
npm --prefix frontend run build
```

### Assumptions Made
- In `frontend/app/page.tsx`, meeting date defaults to a static ISO string (`2026-11-21`) to prevent Next.js 16 SSR/hydration mismatches during static generation.
- Polling in the dashboard runs only while active meetings are in `uploaded` or `processing` state, conserving client/server resources.

### Open Issues / Deferred
- None from Task 8.

