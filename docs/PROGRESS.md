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
│   │           └── trackers.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   ├── test_models.py
│   │   ├── test_seed.py
│   │   ├── test_llm.py
│   │   ├── test_ingestion.py
│   │   ├── test_extraction.py
│   │   └── test_executor.py
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
- Premise break detection algorithms and Review Queue UI to be built in subsequent tasks.
