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
│   │   │   └── extraction.py
│   │   └── api/
│   │       ├── __init__.py
│   │       └── routes/
│   │           ├── __init__.py
│   │           └── meetings.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   ├── test_models.py
│   │   ├── test_seed.py
│   │   ├── test_llm.py
│   │   ├── test_ingestion.py
│   │   └── test_extraction.py
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
- Premise break and cross-meeting conflict detection algorithms to be implemented in Task 6.
