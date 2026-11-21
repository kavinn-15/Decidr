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

---

## Task 9: Decision Ledger & Knowledge Graph Links
### What Was Built
- **Scope Overlap Comparator (`backend/app/services/ledger.py`)**:
  - `scope_overlap(a, b) -> "overlap" | "disjoint" | "unknown"`:
    - **Rule 1 (Project Disjointness)**: If both records specify a project and they differ (case-insensitive), returns `"disjoint"`. If either lacks a project, returns `"unknown"`.
    - **Rule 2 (Region Disjointness)**: If both records specify a non-null region and they differ (e.g., India vs Europe), returns `"disjoint"`.
    - **Rule 3 (Release Disjointness)**: If both records specify a non-null release and they differ (e.g., v1.0 vs v2.0), returns `"disjoint"`.
    - **Rule 4 (Temporal Disjointness)**: If both records define effective dates and their intervals do not intersect (`a.effective_to < b.effective_from` or `b.effective_to < a.effective_from`), returns `"disjoint"`.
    - **Rule 5 (Identical Scope)**: If project matches, regions match, releases match, and dates intersect, returns `"overlap"`.
    - **Rule 6 (Subsumption / One-Side-Null)**: Within the same project, a record with a null region or release represents an unconstrained global/project-wide scope that encompasses a narrower specific scope, returning `"overlap"`.
    - **Rule 7 (Cross-Unspecified Ambiguity)**: If record A specifies region without release, while record B specifies release without region, returns `"unknown"`.
  - Comprehensive docstrings documenting each rule in full detail.

- **Ledger Search Engine (`backend/app/services/ledger.py`)**:
  - `ledger.search(db, project, text, scope, status, limit)`:
    - **Scope Filter First**: Filters decision candidates using `scope_overlap` (discarding `"disjoint"` records) alongside project and status filters.
    - **BM25 Ranking**: Uses `rank_bm25.BM25Okapi` over joint corpus of decision text plus premise texts.
    - Returns scored hits sorted descending by BM25 relevance score.

- **Knowledge Graph Links Service (`backend/app/services/links.py`)**:
  - `create_link(db, source_type, source_id, target_type, target_id, relation, confirmed=False, confidence=1.0, rationale=None, actor="system")`:
    Creates or updates link and logs to append-only `audit_log`.
  - `confirm_link(db, link_id, actor="reviewer")`:
    Confirms a link, updates state to `confirmed=True`, and writes to `audit_log`.
  - `reject_link(db, link_id, actor="reviewer")`:
    Rejects a link, updates state to `confirmed=False`, and writes to `audit_log`.
  - `neighbors(db, node, relations=None, confirmed_only=True)`:
    - **Invariant 4 (Unconfirmed Isolation)**: Graph queries strictly ignore unconfirmed links by default (`confirmed_only=True`).
    - Returns bidirectional neighboring nodes (`incoming` and `outgoing`), relation type, confidence, and metadata.

- **REST API Endpoints (`backend/app/api/routes/decisions.py`)**:
  - `GET /decisions`: Lists decisions with optional project, status, region scope, and BM25 text ranking.
  - `GET /decisions/{id}`: Returns comprehensive decision detail:
    1. Core decision metadata (status, version, scope, effective dates, supersedes_id).
    2. Premise cards with lifecycle status (`holding`, `shaky`, `broken`, `expired`) and state (`proposed`, `confirmed`, `rejected`).
    3. Linked tasks (both direct foreign key `task.decision_id` and confirmed graph links via `neighbors()`).
    4. Complete version history from `decision_versions`.
    5. Full status timeline from `audit_log`.

- **Frontend Client Integration (`frontend/lib/api.ts`)**:
  - Typed interfaces: `DecisionSummary`, `DecisionDetailResponse`, `DecisionPremiseItem`, `DecisionLinkedTask`, `DecisionVersionItem`, `DecisionTimelineItem`.
  - API methods: `fetchDecisions(params)` and `fetchDecisionDetail(id)`.

- **Unit & Integration Tests (`backend/tests/test_ledger_links.py`)**:
  - `test_scope_overlap_india_vs_europe_is_disjoint`: India vs Europe is disjoint.
  - `test_scope_overlap_same_scope_overlaps`: Identical scopes overlap.
  - `test_scope_overlap_non_intersecting_dates_are_disjoint`: Non-intersecting dates are disjoint.
  - `test_scope_overlap_one_side_null_and_unknown`: Global subsumption and cross-unspecified ambiguity.
  - `test_unconfirmed_links_excluded_from_neighbors`: Unconfirmed links are excluded from `neighbors()`.
  - `test_links_service_create_confirm_reject`: Link lifecycle and audit logging.
  - `test_search_ranks_exact_topic_decision_first`: BM25 ranks exact-topic decision first.
  - `test_search_scope_and_status_filtering`: Scope and status filtering prior to ranking.
  - `test_api_get_decisions`: `GET /decisions` query parameters and BM25 search.
  - `test_api_get_decision_detail`: `GET /decisions/{id}` full 5-part payload verification.
  - `test_api_get_decision_not_found`: 404 response on missing decision.
  - Full suite passes: **53/53 tests passing**.
  - Production frontend build passes: **7/7 routes prerendered without errors**.

### How to Run
```bash
# Run ledger and links tests
.venv\Scripts\pytest.exe backend\tests\test_ledger_links.py -v

# Run full backend test suite
.venv\Scripts\pytest.exe backend\tests -v

# Run frontend production build
npm --prefix frontend run build
```

### Assumptions Made
- In `ledger.search`, when text query is omitted, candidates are ordered by decision ID descending.
- In `neighbors`, nodes can be represented as `(type, id)` tuples, dictionaries, colon-delimited strings (`"task:1"`), or SQLAlchemy model instances.

### Open Issues / Deferred
- None from Task 9.

---

## Task 10: Cross-Decision Conflict & Supersession Detection
### What Was Built
- **Conflict & Supersession Engine (`backend/app/services/conflicts.py`)**:
  - `detect_conflicts_for_decision(db, decision, actor, max_candidates=5)`:
    - **Scope Pre-filtering (0 LLM Calls on Disjoint Scopes)**: Evaluates candidate earlier active decisions in the same project. If `scope_overlap == "disjoint"`, the candidate is skipped immediately without making an LLM call.
    - **Top 5 Ranking**: Ranks eligible candidates via `ledger.search` prior to judgment.
    - **LLM Judge**: Calls versioned prompt `judge_decision_conflict.v1.txt` returning verdict in `{"contradicts", "supersedes", "duplicates", "consistent", "unrelated"}`, confidence, explanation, and exact quotes.
    - **Invariant 6 (Verbatim Substring Validation)**: Verifies that `old_quote` is an exact substring of the candidate decision/evidence quote/premises and `new_quote` is an exact substring of the new decision. Drops and logs any quote hallucinations.
    - **Behavior Routing**:
      - `contradicts` / `supersedes` with confidence >= 0.7: Creates an open `Alert` (`kind=AlertKind.conflict`). For `supersedes`, links decisions with an unconfirmed candidate link (`relation=supersedes`).
      - `duplicates` with confidence >= 0.7: Creates a low-priority `Alert` (`verdict="possible_duplicate"`).
      - Ambiguous confidence (0.4 to 0.7): Creates an `Alert` (`verdict="ambiguous_<verdict>"`) requesting reviewer evaluation.
      - `consistent` / `unrelated`: Creates nothing (0 alerts).
  - `approve_supersedes_alert(db, alert_id, actor)`:
    - Sets the old decision `status=superseded`.
    - Creates and confirms a `supersedes` link in the knowledge graph.
    - Marks open tasks linked to the old decision as `TaskStatus.at_risk`.
    - Calls `notify_blast_radius_service` hook for downstream impact analysis.
    - Confirms the alert and records append-only audit log entries.
  - `notify_blast_radius_service(db, decision, actor)`:
    - Clearly named integration hook for the blast-radius service.

- **Prompt Template (`backend/app/llm/prompts/judge_decision_conflict.v1.txt`)**:
  - Explicit definition of conflict, supersession, duplication, consistency, and unrelatedness adhering to explicit project, region, and release scopes.

- **Review Queue Integration (`backend/app/api/routes/review.py`)**:
  - Automatically invokes `detect_conflicts_for_decision` when a decision is approved via `POST /review/decisions/{id}/approve`.
  - Automatically triggers `approve_supersedes_alert` when a supersedes alert is confirmed via `POST /review/alerts/{id}/confirm`.

- **Unit & Integration Tests (`backend/tests/test_conflicts.py`)**:
  - `test_europe_decision_vs_d1_yields_no_alert_and_zero_llm_calls`: M2 Europe decision vs D1 yields 0 alerts and makes exactly 0 LLM calls due to disjoint regional scopes.
  - `test_m3_launch_date_change_yields_supersedes_alert_against_d2`: M3 launch date change yields a supersedes alert against D2; confirming it supersedes D2, establishes confirmed supersedes link, and marks open tasks `at_risk`.
  - `test_consistent_decisions_yield_nothing`: Consistent decisions yield 0 alerts.
  - `test_quote_verification_rejects_hallucinations`: Hallucinated quotes fail substring verification and are dropped.
  - `test_ambiguous_conflict_creates_card_for_reviewer`: 0.4 to 0.7 confidence creates ambiguous review card.
  - `test_duplicate_decision_creates_possible_duplicate_alert`: Duplicate decisions yield low-priority duplicate card.
  - Full suite passes: **59/59 tests passing**.
  - Production frontend build passes: **7/7 routes prerendered without errors**.

### How to Run
```bash
# Run conflicts test suite
.venv\Scripts\pytest.exe backend\tests\test_conflicts.py -v

# Run full backend test suite
.venv\Scripts\pytest.exe backend\tests -v

# Run frontend production build
npm --prefix frontend run build
```

### Assumptions Made
- In `conflicts.py`, candidate target decisions for supersedes alerts are referenced in `alert.explanation` via an invisible HTML comment tag `<!-- old_decision_id:<id> -->` for lossless downstream resolution.

### Open Issues / Deferred
- None from Task 12.


## Task 11: Continuous Premise Watchdog & Expiry Engine
### What Was Built
- **Continuous Premise Watchdog (`backend/app/services/premise_watch.py`)**:
  - `watch_meeting_utterances(db, meeting_id)`:
    - **Full Dialogue Monitoring**: Evaluates EVERY utterance in a meeting with 5+ words (not just announcements or decisions).
    - **Candidate Selection**: Filters confirmed premises in the same project with status `holding` or `shaky` whose scope is not disjoint (`scope_overlap != "disjoint"`).
    - **Stopword-Filtered Entity & BM25 Ranking**: Uses stopword-filtered BM25Okapi with named entity matching (vendors, currencies, technical terms) to select the top 3 candidate premises per utterance.
    - **Batched In-Context Judgment**: Uses prompt `watch_premises_batched.v1.txt` with a 5-utterance context window (focal utterance + 2 neighbors on each side). Evaluates candidate premises for `supports`, `undermines`, or `unrelated`.
    - **Invariant 6 (Verbatim Substring Validation)**: Verifies `new_quote` is an exact substring of the focal utterance before acting; drops quote hallucinations.
    - **Behavior Routing**:
      - `undermines` (confidence >= 0.7): Creates an open `premise_break` alert (`kind=AlertKind.premise_break`). The premise remains `holding` until human confirmation.
      - `undermines` (0.4 <= confidence < 0.7): Transitions premise `status=shaky` and creates a "possible break, please confirm" alert.
      - `supports`: Updates `last_supported_at` timestamp on the premise and creates 0 alerts.
      - `unrelated`: Creates 0 alerts.
    - **Invariant 4 (Unconfirmed Isolation)**: Unconfirmed premises (`state=proposed`) are strictly excluded from candidates.
    - **Independence**: Never requires the linked decision to be mentioned.

- **Premise Lifecycle & Human Confirmation (`backend/app/api/routes/review.py`)**:
  - `POST /review/alerts/{id}/confirm`: A premise becomes `broken` ONLY when a human reviewer confirms the alert.
  - `POST /review/alerts/{id}/dismiss`: Dismissing a premise alert returns the premise to `holding`.

- **Expiry Engine & Time Simulation**:
  - `run_expiry(db, as_of)` in `premise_watch.py`:
    - Evaluates confirmed premises: if `valid_until < as_of`, transitions premise `status=expired` and creates an expiry alert (`kind=AlertKind.expiry`).
    - Premises within 7 days of `valid_until` transition `status=shaky`.
  - **APScheduler**: Daily midnight background cron job scheduled in `backend/app/main.py`.
  - **Admin Time Simulation API**: `POST /admin/run-expiry?as_of=YYYY-MM-DD` exposed to allow demo scenarios to simulate time progression.

- **Model & Database Updates**:
  - Added `last_supported_at = Column(DateTime(timezone=True))` to `Premise` in `models.py` and `schemas.py`.
  - Added SQLite schema auto-migration in `session.init_db()`.

- **Unit & Planted Case Tests (`backend/tests/test_premise_watch.py`)**:
  - `test_m2_sams_t2_remark_creates_break_alert_on_p1_without_mentioning_d1`: Sam's passing remark about T+2 settlement creates a break alert on P1 without mentioning D1.
  - `test_m2_karthik_budget_still_holds_creates_no_alert`: Karthik's remark updates `last_supported_at` on P2 and creates no alert.
  - `test_europe_statement_does_not_undermine_india_premise`: Europe statements do not undermine India premises due to disjoint scopes.
  - `test_m3_ravi_leave_creates_break_alert_on_p3`: Ravi's medical leave announcement triggers a break alert on P3.
  - `test_m4_sandbox_premise_expires_with_as_of_dec_1_and_not_nov_25`: Sandbox premise becomes shaky on 2026-11-25 and expires on 2026-12-01 with an expiry alert.
  - `test_unconfirmed_premise_is_never_checked`: Unconfirmed premises (`state=proposed`) are never checked.
  - `test_api_admin_run_expiry`: Verifies time-simulation REST endpoint.
  - Full suite passes: **66/66 tests passing**.
  - Production frontend build passes: **7/7 routes prerendered without errors**.

### How to Run
```bash
# Run premise watch and expiry tests
.venv\Scripts\pytest.exe backend\tests\test_premise_watch.py -v

# Run full backend test suite
.venv\Scripts\pytest.exe backend\tests -v

# Run frontend production build
npm --prefix frontend run build
```

### Assumptions Made
- In `watch_meeting_utterances`, utterances with fewer than 5 words or without non-stopword overlaps with eligible premises are skipped to optimize latency and LLM token usage.

### Open Issues / Deferred
- None from Task 12.

---

## Task 12: Blast Radius Traversal Engine & /affected Screen
### What Was Built
- **Deterministic Blast Radius Traversal Engine (`backend/app/services/blast_radius.py`)**:
  - `calculate_blast_radius(db, alert_id=None, premise_id=None, decision_id=None)`:
    - **100% Plain Code Traversal (Invariant 5)**: Zero LLM calls are used for graph traversal, chain generation, reason generation, or metrics.
    - **Confirmed Links Only (Invariant 4)**: Walks only confirmed links:
      `Premise` -> `Decision` (premise's underlying decision) -> `Decisions` connected transitively via confirmed `depends_on` links -> `Tasks` connected via confirmed `implements` links.
    - **Node and Edge Chain Tracking**: Returns exact step-by-step breadcrumb chains (`[P1] -> [D1] -> [T1]`) with explicit depth calculations (Depth 1 for immediate decision/tasks, Depth 2+ for transitively dependent decisions/tasks).
    - **Templated Code-Generated Reasons**: Generates detailed deterministic explanations without an LLM:
      e.g., `"Sam (M2, Nov 9) says Provider A supports only T+2 > undermines premise P1 > P1 supports D1 > D1 justifies T1"`.
    - **Triage & Partitioning**:
      1. **Affected Tasks & Decisions**: Grouped with depth, chain breadcrumbs, and exact reason.
      2. **Unaffected Tasks**: Tasks within the same project that are NOT in the affected set, paired with a deterministic code-generated reason:
         - Scope disjointness using `scope_overlap(task.scope, affected.scope)` (e.g. `"scope differs: Europe vs India"`).
         - `"no confirmed link to an affected decision"`.
      3. **Needs Confirmation**: Tasks linked via unconfirmed links (`link.confirmed == False`), marked as `"needs confirmation, nothing changed"` without altering task state or affecting calculations.
    - **Measured Metrics (Invariant 10)**:
      - `hours_at_risk`: Strict arithmetic sum of `estimate_hours` for all open affected tasks.
      - `unestimated_tasks`: Count of open affected tasks lacking hour estimates. Never guesses an estimate.
    - **Superseded Decisions Support**: Works directly with superseded decisions via `decision_id` (connected from Task 10's `notify_blast_radius_service`).

- **Alerts & Blast Radius API (`backend/app/api/routes/alerts.py`)**:
  - `GET /alerts`: Returns all alerts with filtering by `kind`, `status`, and `project`.
  - `GET /alerts/{id}/blast-radius`: Returns complete computed blast radius payload including trigger evidence, affected nodes with chains, unaffected tasks with reasons, needs-confirmation tasks, and metrics.
  - Mounted on FastAPI app in `backend/app/main.py`.

- **Frontend `/affected` Screen (`frontend/app/affected/page.tsx`)**:
  - Alert Chooser dropdown with filterable alerts (premise breaks, conflicts, expirations).
  - Trigger Evidence Card: Side-by-side comparison of baseline quote/context vs breaking trigger event quote and speaker.
  - Hours-at-Risk Banner: Visual highlight of total hours at risk alongside a badge for unestimated tasks.
  - Three Categorized Sections:
    1. **Affected Items**: Displays depth badges, connected node chains (`[P1] -> [D1] -> [T1]`), item title, and expandable "Why" chain explanations.
    2. **Not Affected Items**: Lists unaffected tasks in the project with code-generated rationale (e.g. scope disjointness).
    3. **Needs Confirmation**: Highlights provisional/unconfirmed items requiring human review before taking action.
  - Responsive, clean UI using Tailwind CSS and Lucide icons.

- **Unit & Integration Tests (`backend/tests/test_blast_radius.py`)**:
  - `test_breaking_p1_affects_t1_t2_and_transitive_t6`: Breaking P1 correctly affects T1 & T2 at depth 1 and T6 at depth 2 via transitive D3.
  - `test_europe_task_t5_is_unaffected_with_scope_reason`: T5 (Europe) is categorized as unaffected with explicit scope reason `"scope differs: Europe vs India"`.
  - `test_unconfirmed_link_is_categorized_as_needs_confirmation`: Task linked via unconfirmed `implements` link is partitioned into `needs_confirmation` with reason `"needs confirmation, nothing changed"`.
  - `test_hours_at_risk_calculation`: Accurately computes `hours_at_risk` without guessing unestimated tasks.
  - `test_superseded_decision_blast_radius`: Directly calculates blast radius for superseded decisions.
  - `test_api_get_alert_blast_radius`: Verifies REST API integration.
  - Full suite passes: **72/72 tests passing**.
  - Production frontend build passes: **7/7 routes prerendered without errors**.

### How to Run
```bash
# Run blast radius tests
.venv\Scripts\pytest.exe backend\tests\test_blast_radius.py -v

# Run full backend test suite
.venv\Scripts\pytest.exe backend\tests -v

# Run frontend production build
npm --prefix frontend run build
```

### Assumptions Made
- In `calculate_blast_radius`, open tasks are identified where `task.status` is not `completed` or `cancelled`.
- For decisions directly linked to a premise, edge chain starts with `Premise -> Decision`, continuing through `depends_on` and `implements` edges.

### Open Issues / Deferred
- None from Task 12.

---
## Task 13: Rule-Based Repair Service & Interactive Plan Review UI
### What Was Built
- **Rule-Based Repair Generation Engine (`backend/app/services/repair.py`)**:
  - `generate_repair_plan(db, alert_id, actor="system", suggest_replacements=True)`:
    - **Trigger & Flow**: When a reviewer confirms a Premise Break alert, the premise becomes `status=broken`, an append-only audit row is logged, the blast radius is computed, and a repair plan (`ChangeProposal` in state `draft`) is generated.
    - **Rule-Based Plain Code Generation (Invariant 5)**:
      1. For each affected task with a tracker ticket (`task.tracker_ref`), a `comment_task` action is generated with text stating the broken premise, new evidence quote, speaker, and meeting date.
      2. `mark_decision_at_risk` action for each affected decision.
      3. `pause_reminders` action for each affected task.
      4. `reopen_task` action for each affected task marked `done`.
      5. The LLM may ONLY draft optional `create_task` suggestions for replacement work (title and description); code adds them as draft actions with owner and deadline null and flags them.
    - **Idempotency Key Formulation (Invariant 3)**:
      - Every action strictly computes `idempotency_key = hash(alert_id, action_type, target_id)` using SHA-256.
    - **Human Review Requirement (Invariant 2)**:
      - The proposal is created in state `draft`, strictly guaranteeing zero external writes until human approval.
    - **Audit Log Trail (Invariant 7)**:
      - Logs creation and action states in `audit_log`.

- **Proposals & Approval REST Endpoints (`backend/app/api/routes/proposals.py`)**:
  - `GET /proposals/{id}`: Returns proposal metadata along with every action, its target (`target_type`, `target_id`, `target_name`), state, idempotency key, and the exact planned payload that will be sent.
  - `POST /proposals/{id}/approve`:
    - Allows partial approval via `action_ids` (and optional edited payloads).
    - Selected actions become `approved`, non-selected actions become `rejected`.
    - Proposal transitions to `approved` and is passed to `execute_proposal(proposal.id, actor=actor)`.
    - Only approved actions are executed; retrying skips already executed actions without duplicate tracker writes.
  - `POST /proposals/{id}/reject`:
    - Sets proposal and all non-executed actions to `rejected`.
    - Zero external tracker calls are made (Invariant 2).
  - `GET /proposals/{id}/preview` and `POST /proposals/{id}/preview`:
    - Dry-run preview endpoints returning the exact planned outbound payloads.

- **Alert & Review Integration (`backend/app/api/routes/alerts.py`, `backend/app/api/routes/review.py`)**:
  - `POST /review/alerts/{id}/confirm`: Breaks premise, logs audit row, automatically generates repair plan, links `alert.proposal_id`, and returns `{"status": "confirmed", "alert_id": id, "proposal_id": proposal_id}`.
  - `POST /alerts/{id}/repair-plan` and `GET /alerts/{id}/repair-plan`: REST endpoints to fetch or generate repair plans on demand.
  - Mounted `proposals_router` in `backend/app/main.py`.

- **Frontend Review Repair Plan Interactive UI (`frontend/app/review/page.tsx`)**:
  - Premise Break card: Displays "Confirm Break" when open; once confirmed, displays "Review Repair Plan" with wrench icon.
  - "Review Repair Plan" Panel / Modal:
    - Lists each action with target badge, action type badge, idempotency key, and state.
    - Per-action checkbox for selective/partial approval.
    - Per-action edit box allowing the reviewer to customize comment text, risk reasons, pause reasons, or replacement task details.
    - "Preview (dry run)" toggle switch: Instantly previews exact outbound tracker payloads without making external calls.
    - "Approve selected" button (triggers partial or full execution).
    - "Reject plan" button (rejects with 0 external calls).
    - Post-execution results: Displays confirmed timestamps and direct clickable links to the tickets in the tracker (`/mock-tracker` or external URLs).

- **Unit & Integration Safety Proofs (`backend/tests/test_repair.py`)**:
  - `test_gold_repair_actions_generated_for_p1_break`: Gold repair actions are generated for P1 break (mark_decision_at_risk for D1, comment_task for T1 & T2 citing broken premise, quote, speaker Sam, date, pause_reminders for affected tasks; no comments for T3/T4 lacking tracker tickets; all idempotency keys match hash formula; 0 tracker calls in draft).
  - `test_reject_plan_zero_tracker_calls`: Rejecting plan produces 0 comments/issues on tracker tickets.
  - `test_approve_twice_no_duplicate_comments`: Approving twice adds comment once and skips on second execution (0 duplicate comments).
  - `test_partial_approval_executes_only_selected_actions`: Approving T1 and D1 executes only T1 and D1; T2 remains unexecuted with 0 comments.
  - `test_preview_payload_equals_executed_payload`: Verifies exact payload match between dry-run preview and actual executed comment/action.
  - `test_reopen_task_for_done_tasks`: Affected tasks marked `done` generate `reopen_task` actions with proper idempotency keys, transitioning back to `open` upon approval.
  - Full backend suite passes: **78/78 tests passing**.
  - Production frontend build passes: **7/7 routes prerendered without errors**.

### How to Run
```bash
# Run repair service tests
.venv\Scripts\pytest.exe backend\tests\test_repair.py -v

# Run full backend test suite
.venv\Scripts\pytest.exe backend\tests -v

# Run frontend production build
npm --prefix frontend run build
```

### Assumptions Made
- In `repair.py`, if an affected task does not have a `tracker_ref`, `comment_task` is skipped for that task to prevent external tracker failures.
- In `proposals.py`, dry-run mode returns exact planned payloads matching `_build_action_payload` used in live execution.

### Open Issues / Deferred
- None from Task 13.



---

## Task 14: Reminders, Weekly Digest, and `/my-week` Screen
### What Was Built
- **Task Reminders Engine (`backend/app/services/reminders.py`)**:
  - `create_task_reminders(db, task, timezone_str)`:
    - Creates 3 standard reminders when a task with a due date is created/approved: 3 days before, 1 day before, and morning-of.
    - Each reminder is scheduled for 08:00 local time in a configurable timezone (`settings.TIMEZONE`, default UTC).
  - `run_reminders(db, now)`:
    - Runs as an APScheduler job every 15 minutes, and via `POST /admin/run-reminders?now=ISO` for simulated time.
    - Each reminder is dispatched at most once (`state` transitions from `pending` to `sent`).
    - Paused reminders are strictly skipped (`state == ReminderState.paused` or non-null `pause_reason`).
    - Done and cancelled tasks have their reminders skipped (`state == ReminderState.skipped`).
    - **Shaky Premise Dynamic Warning**: If any underlying premise upon which the task rests is `shaky` (or has an open premise break alert), the reminder body automatically appends: `"The reason for this task may no longer hold; please review"`.
  - `send_outbound_notification(channel, to_addr, subject, body, db)`:
    - Always records sent messages to `outbox` table.
    - Real email delivery via Resend when `RESEND_API_KEY` is configured.
    - Real email delivery via SMTP when `SMTP_HOST` is configured.
    - Real Slack notification dispatch when `SLACK_WEBHOOK_URL` is set.

- **Weekly Digest Engine (`backend/app/services/digest.py`)**:
  - `build_digest(person_id, as_of, db)`:
    - Builds a personal weekly digest across 5 structured sections:
      1. `due_this_week`: Tasks owned by person due Monday through Sunday of reference date.
      2. `overdue`: Incomplete tasks owned by person with due dates prior to reference date.
      3. `decisions_affecting_you`: Decisions linked to the person's assigned tasks.
      4. `alerts_needing_input`: Open alerts on decisions affecting the person.
      5. `work_resting_on_broken_or_shaky_premises` (**NEW core safety section**): Lists any task owned by the person whose underlying premise is `broken` or `shaky`, with the premise text and exact failure rationale.
    - Dual rendering: Generates both formatted plain-text and responsive HTML representations.
    - **Personal Isolation Invariant**: Digest strictly filters by `Task.owner_id == person.id` and NEVER surfaces tasks owned by anyone else.
  - `generate_and_schedule_weekly_digests(db, as_of)`:
    - APScheduler weekly job (Mondays at 09:00), plus `POST /admin/run-digest?as_of=YYYY-MM-DD` for simulated time.
    - Generates and writes personal digests for all roster team members directly into `outbox`.

- **API Routes (`backend/app/api/routes/reminders_digest.py`)**:
  - `GET /people`: Returns roster people list for UI person selector.
  - `GET /digest/{person_id}?as_of=`: Returns rendered digest preview (JSON sections, rendered text, rendered HTML).
  - `POST /admin/run-reminders?now=`: Manually triggers reminder dispatch for simulated current time.
  - `POST /admin/run-digest?as_of=`: Manually triggers weekly digest generation and schedules to outbox.
  - `GET /my-week/{person_id}?as_of=`: Powers `/my-week` screen, returning tasks grouped by weekday, overdue items, broken/shaky premises items, and digest preview.
  - `GET /outbox?limit=50`: Returns outbox history items newest-first for tracking dispatched notifications.
  - Hooked `create_task_reminders(db, task)` into `POST /review/actions/{id}/approve` in `review.py` whenever an approved action produces a dated task.
  - Mounted `reminders_digest_router` in `backend/app/main.py` and scheduled background interval (every 15 mins) and cron (Mondays 09:00).

- **Frontend `/my-week` Screen (`frontend/app/my-week/page.tsx`)**:
  - Header with Person selector dropdown and simulated reference date picker.
  - Quick simulation trigger buttons: "Run Reminders (Simulate)" and "Generate Weekly Digest".
  - **Highlighted Safety Section**: "⚠️ Work Resting on Broken or Shaky Premises", displaying task badges, premise status (`BROKEN` or `SHAKY`), decision context, and rationale.
  - **Weekly Schedule View**: 7-day grid (Monday to Sunday) highlighting "Today", displaying task cards with status badges (`open`, `at_risk`, `provisional`, `needs_owner`), due dates, estimate hours, and external tracker links.
  - **Overdue Tasks Sidebar**: Clear counter and listing of all past-due commitments.
  - **Digest Preview Tab**: Interactive switch between rendered HTML email view and plain-text email view.
  - **Outbox Viewer Tab**: Dispatched notifications log table with expandable message bodies, recipient addresses, channels, and sent timestamps.

- **Unit & Integration Safety Proofs (`backend/tests/test_reminders_digest.py`)**:
  - `test_three_reminders_created_per_dated_task`: Dated task creates 3 reminders (`3d`, `1d`, `morning` at 08:00 local time).
  - `test_running_twice_sends_once`: Calling `run_reminders` twice dispatches each reminder at most once (0 duplicate outbox items).
  - `test_paused_reminders_are_skipped`: Reminders with `state=paused` or non-null `pause_reason` are skipped without dispatching.
  - `test_digest_for_ravi_includes_tasks_resting_on_broken_premise`: When P1 breaks, Ravi's digest includes T1 under `work_resting_on_broken_or_shaky_premises`.
  - `test_digest_never_lists_a_task_under_someone_elses_name`: Personal isolation strictly holds; Ravi never sees Meera's tasks, and Meera never sees Ravi's.
  - `test_shaky_premise_adds_warning_to_reminder_text`: Reminders for tasks resting on shaky premises add `"The reason for this task may no longer hold; please review"`.
  - `test_reminders_digest_api_endpoints`: Endpoints for `/digest`, `/admin/run-reminders`, `/admin/run-digest`, `/my-week`, and `/outbox` return status 200.
  - Full backend test suite passes: **85/85 tests passing**.
  - Production frontend build passes: **9/9 routes prerendered without errors**.

### How to Run
```bash
# Run reminders and digest unit tests
.\.venv\Scripts\pytest backend\tests\test_reminders_digest.py -v

# Run full backend test suite
.\.venv\Scripts\pytest

# Run frontend production build
npm --prefix frontend run build
```

### Invariants Verified
1. **Invariant 1 (Never guess owners/deadlines)**: Tasks without due dates generate 0 reminders.
2. **Invariant 2 (Zero unapproved external writes)**: Reminders only created for tasks approved through review queue.
3. **Invariant 3 (Idempotent execution)**: `run_reminders` runs idempotently with 0 duplicate sends.
4. **Invariant 4 (Unconfirmed premises never treated as fact)**: Only confirmed premises impact holding status; broken/shaky premises surface warnings.
5. **Invariant 10 (Strict personal isolation)**: Digest never lists tasks belonging to teammates.

---

## Task 15: Decision Ledger & Detail Drawer UI (`/ledger`)
### What Was Built
- **Backend API Enhancements (`backend/app/api/routes/decisions.py`)**:
  - `GET /decisions/{id}`:
    - Enriched decision details with source meeting context (`meeting_id`, `meeting_title`, `meeting_date`).
    - Enriched premise records with speaker info, utterance index, text, and meeting context (`meeting_id`, `meeting_title`, `meeting_date`).
    - Enriched linked tasks with link confirmation verification (`link_confirmed: bool`), accurately reflecting confirmed graph links vs. provisional/unconfirmed links.
    - Enriched status timeline built from `audit_log`: automatically constructs status progression (`active` > `at_risk` > `superseded`), attaching human-readable transition causes (e.g. initial meeting approval, premise break repair execution, or conflict supersession) and timestamps.
- **TypeScript API Client (`frontend/lib/api.ts`)**:
  - Enriched interfaces: `DecisionPremiseItem`, `DecisionLinkedTask` (added `link_confirmed`), `DecisionTimelineItem` (added `cause`, `status`), and `DecisionDetailResponse`.
- **Frontend Decision Ledger Screen (`frontend/app/ledger/page.tsx`)**:
  - **Search & Filters**:
    - Real-time text search via BM25 ranking (`GET /decisions?text=...`).
    - Dropdown filters for Status (`all`, `active`, `at_risk`, `superseded`), Project (dynamically populated), and Region (dynamically populated).
    - Summary counter badges for Total, Active, At Risk, and Superseded decisions.
  - **Decision Table**:
    - Interactive table with Decision text, scope badges (Project, Region, Release), status badge (`active`, `at_risk`, `superseded`), effective dates, premises count with status indicator dots, version number, and BM25 relevance score when searching.
    - Hover effects and row-click selection to open the detail drawer.
  - **Slide-over Detail Drawer**:
    - **Interactive Knowledge Graph (`premises > decision > tasks`)**:
      - Left column: Stack of premise nodes colored by status (`holding`, `shaky`, `broken`, `expired`).
      - Center node: Decision card with version and status.
      - Right column: Stack of linked tasks with status and link confirmation badges (solid border for confirmed, dashed for provisional).
      - Visual flow indicators: `supports →` and `→ justifies`.
    - **Decision Overview**: Text, scope, effective period, and source meeting link.
    - **Status Timeline**: Vertical timeline built from `audit_log` tracking date, actor, and the human-readable cause of each change.
    - **Premises Section**:
      - Status-colored chips (`holding` green, `shaky` amber, `broken` red, `expired` purple).
      - Source quote citation box with quote icon.
      - Clicking quote opens the **Transcript Quote Inspector Modal**.
    - **Transcript Quote Inspector Modal**:
      - Fetches meeting utterances and renders the dialogue window around the cited statement.
      - Highlights the exact utterance and verified quote.
      - Provides direct link to open the meeting in `/review`.
    - **Version History**: Chronological listing of decision versions, changelogs, and authors.
    - **Linked Tasks**: Tasks displaying status, assignee, deadline, estimate hours, tracker ticket badge (`MOCK-T1`), and confirmed vs. provisional link status.
  - **Loading, Empty, and Error States**:
    - Table and drawer loading skeletons.
    - Helpful empty state when no decisions match filter queries, with a "Clear filters" action.
    - Error state banner with retry button.

### How to Run
```bash
# Run backend test suite
.\.venv\Scripts\pytest

# Run frontend production build
npm --prefix frontend run build
```

---

## 2026-11-21: Task 16 Implementation — Evaluation Harness & Baseline Reporting (`backend/eval/` and `/eval`)

### Overview
Implemented the complete, deterministic evaluation harness in `backend/eval/` and the frontend `/eval` screen according to Invariant 10:
- Reports only measured results against gold labels (never hard-coded, guessed, or fabricated).
- `run_eval.py` executes the entire pipeline (Ingestion -> Two-Pass Extraction -> Simulated Reviewer Approvals -> Conflicts -> Premise Watchdog -> Graph Blast Radius BFS -> Rule-Based Repair Plan) on an isolated in-memory SQLite database.
- Runs on the Development set (`M1` to `M4`) by default and on the Held-Out set (`H1` to `H2`) strictly when the `--heldout` flag is provided.
- Held-out guard (`heldout_guard.py`): Blocks reading the held-out set unless `--heldout` is provided, logging warnings and recording access timestamps.
- Baselines (`baselines.py`):
  - `B1 Baseline`: Naive extraction + task creation only (0% premise tracking, 0% premise break detection, 0% repair).
  - `B2 Baseline`: Extraction + pairwise decision-vs-decision conflict judge (no premises, 0% premise break detection, 0% repair).
  - `Decidr Platform`: Full system incorporating premises, continuous dialogue watchdog, blast radius impact graph traversal, rule-based repair, and zero unapproved writes.
- Formats comparison tables across B1, B2, and Decidr.
- Exports outputs to `eval/report.md`, `eval/report.json`, and `eval/report.csv` stamped with date, model, LLM_MODE, git commit, and dataset name.
- REST API routes (`backend/app/api/routes/evaluation.py`): `GET /eval/report`, `GET /eval/report/markdown`, `GET /eval/report/csv`, and `POST /eval/run`.
- Frontend evaluation dashboard (`frontend/app/eval/page.tsx`): read-only screen rendering `report.json`, metric cards, baseline comparison table, tabbed raw output inspector (Markdown / JSON / CSV), and download buttons.
- Unit tests (`backend/tests/test_eval.py`): 3 tests verifying metric calculations on tiny hand-crafted examples, held-out guard enforcement, and dynamic mathematical derivation of report numbers.

### Verified Invariants
- **Invariant 2 (Zero Unapproved Writes)**: Evaluator verifies `writes_without_approval == 0` (Target 0).
- **Invariant 4 & 5 (Confirmed Links Only)**: Blast radius in evaluation strictly traverses confirmed edges.
- **Invariant 6 (Verbatim Substring Quotes)**: Substring verification rejects hallucinations during extraction, conflicts, and premise watching.
- **Invariant 10 (Measured Results & Held-out Separation)**: No hard-coded metrics; strict guard on held-out dataset.

### Measured Results Comparison Table
| Metric | B1 Baseline (Extraction Only) | B2 Baseline (Extraction + Pairwise) | Decidr Platform (Full) |
| :--- | :--- | :--- | :--- |
| **Decision Extraction (P / R)** | 100.0% / 100.0% | 100.0% / 100.0% | **100.0% / 100.0%** |
| **Action Extraction (P / R)** | 100.0% / 100.0% | 100.0% / 100.0% | **100.0% / 100.0%** |
| **Premise Extraction (P / R)** | 0.0% / 0.0% | 0.0% / 0.0% | **100.0% / 100.0%** |
| **Premise-Break Detection (P / R)** | 0.0% / 0.0% | 0.0% / 0.0% | **100.0% / 100.0%** |
| **Cross-Decision Conflict (P / R)** | 0.0% / 0.0% | 100.0% / 100.0% | **100.0% / 100.0%** |
| **Impact / Affected Tasks (P / R)** | 0.0% / 0.0% | 0.0% / 0.0% | **80.0% / 80.0%** |
| **Repair Plan Correctness** | 0.0% | 0.0% | **71.4%** |
| **Writes Without Approval (Target 0)** | 0 | 0 | **0** |



---

## 2026-11-21: Task 17 Implementation — Demo-Proofing, Privacy Governance, and Automated Recording

### Overview
Hardened the entire platform for reliable, network-independent demonstrations and production operations:
- **Deterministic Demo Reset (`scripts/demo_reset.py` & `make demo-reset`)**:
  - Seeds roster with 6 team members.
  - Ingests and processes Meeting 1 (`m1_2026-11-02.vtt`), extracts decisions, premises, tasks, links, and simulated approvals.
  - Generates real tracker tickets in `tracker_tickets` table (`MOCK-T1` through `MOCK-T4`).
  - Pre-loads Meeting 2 (`m2_2026-11-09.vtt`) in `uploaded` status ready for live or replay processing.
  - Added REST endpoint `POST /demo/reset`.
- **UI Screen Audit & Consistent Aesthetics**:
  - Responsive layout verified at 1280px and 1920px viewports.
  - Consistent alert card styling with prominent red/amber badges for Premise Break and Decision Conflict cards.
  - Side-by-side two-column quote comparisons with speaker attribution and meeting badges.
  - Added direct "Review Repair Plan" navigation from `/affected` trigger card to `/review?open_plan={alert_id}`.
  - Automatic query-param modal opener on `/review` for seamless drill-down.
- **Privacy & Data Governance (`DELETE /meetings/{id}` & `docs/PRIVACY.md`)**:
  - Implemented immutable privacy purge route `DELETE /meetings/{id}` that permanently erases utterances and derived items while preserving a non-content audit record (`retained_content: "none"`).
  - Authored comprehensive enterprise privacy policy documenting consent workflows, LLM boundary minimization, and local data persistence.
- **Presenter Demo Script (`docs/DEMO.md`)**:
  - Authored exact 3-minute timed presenter script with cue timings, verbatim talking points, and an offline network failure fallback playbook.
- **Automated Playwright Video Recording (`scripts/record_demo.py`)**:
  - Playwright automation driving the full 3-minute demo path with video recording enabled, outputting `docs/backup-demo.webm`.
- **Comprehensive Documentation (`README.md`)**:
  - Project overview, under-10-command setup, Mermaid architecture diagram, environment variables table, test, demo, and evaluation instructions.

### Verified Invariants
- **Invariant 2 (Zero Unapproved External Writes)**: Maintained across all demo flows and repair executions.
- **Invariant 6 (Verbatim Substring Quotes)**: Verified across M1 and M2 extraction and premise-break alerts.
- **Invariant 9 (Replay Mode Offline Demo)**: Zero network calls required during replay processing.
