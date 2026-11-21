# PROGRESS & IMPLEMENTATION LOG

## Repository Layout
```
decidr/
├── .env.example
├── .gitignore
├── Makefile
├── docs/
│   └── PROGRESS.md
├── scripts/
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
│   │   │   └── ingestion.py
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
│   │   └── test_ingestion.py
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
### What Was Built
- Backend FastAPI app with `GET /health` returning `{"status":"ok"}`.
- Settings configuration using `pydantic-settings` reading `.env` with all specified defaults and variables.
- CORS middleware configured for `http://localhost:3000`.
- Pytest testing setup with initial health check test.
- LLM Adapter architecture in `backend/app/llm/adapter.py` caching responses deterministically on disk keyed by `hash(model, prompt, input)`.
- Frontend Next.js App Router application with Tailwind CSS and Lucide icons.
- Left sidebar layout navigation across all six routes (`/`, `/review`, `/affected`, `/ledger`, `/my-week`, `/audit`).
- Typed API client in `frontend/lib/api.ts` accessing `NEXT_PUBLIC_API_URL`.
- Root configuration: `Makefile` (`dev`, `test`, `seed`, `reset`, `eval`), `.env.example`, `.gitignore`, initialized git repository.

---

## Task 2: Data Models, Schemas & Append-Only Audit Log
### What Was Built
- **SQLAlchemy 2.0 ORM Models** for all 15 entities (`backend/app/models/models.py`).
- **String Enums** for every state and relation field (`backend/app/models/enums.py`).
- **SQLite Foreign Key Enforcement** in `backend/app/db/session.py` via connection listener.
- **Append-Only Audit Log Guard** enforcing that any `UPDATE` or `DELETE` on `audit_log` raises `ReadOnlyAuditLogError` (Invariant 7).
- **Audit Service** in `backend/app/services/audit.py` implementing `log(actor, action, entity_type, entity_id, before, after)`.
- **Pydantic v2 Schemas** in `backend/app/schemas/schemas.py` providing typed Base, Create, and Read schemas for all 15 models.
- **Database Reset Scripts** (`scripts/reset_db.py`, `scripts/reset-db`, `scripts/reset-db.bat`).
- **Unit and Integration Tests** (`backend/tests/test_models.py`).

---

## Task 3: Seed Data & Evaluation Ground Truth
### What Was Built
- **Team Roster** in `backend/seed/roster.json`: Asha (PM), Ravi (backend), Meera (frontend), Karthik (finance), Divya (QA), Sam (vendor manager) with tracker IDs and emails under the "Payments Revamp" project.
- **Natural, Messy WebVTT Transcripts**:
  - `m1_2026-11-02.vtt`: Kickoff meeting with tangents and coffee banter. Buries decisions D1 (Provider A for India), D2 (launch Dec 15), premises P1 (T+0 settlement), P2 (8 lakh budget), P3 (Ravi available full-time until Dec 5), action items T1-T5 (including missing deadline and missing owner cases), and an ambiguous SLA review task.
  - `m2_2026-11-09.vtt`: Weekly sync where Sam mentions in passing that Provider A only supports T+2 settlement (breaks P1 without naming D1). Karthik confirms 8 lakh budget holds (false positive test). Asha decides Provider B for Europe (different region, no conflict under Invariant 9).
  - `m3_2026-11-16.vtt`: Explicit timeline shift moving launch from Dec 15 to Jan 10 (supersedes D2). Decision D3 adds reconciliation report checklist (depends on D1). Action T6 prepares checklist (two links from P1). Ravi mentions leave starting Dec 1 (undermines P3).
  - `m4_2026-11-23.vtt`: Decision to use Provider A sandbox with premise that access is valid until Nov 30 (scheduled expiry case without contradiction).
- **Held-Out Evaluation Transcripts** in `backend/seed/heldout/`:
  - Separate project "Mobile App Release" with dedicated roster (`roster_heldout.json`), transcripts `h1_2026-10-05.vtt` and `h2_2026-10-12.vtt`, and ground truth labels (`gold_labels_heldout.json`).
- **Comprehensive Ground Truth** in `backend/seed/gold_labels.json`:
  - Complete specifications for decisions, premises, actions, links, expected alerts, multi-hop blast radius, and repair actions.
- **Database Seeding Script** in `scripts/seed.py`:
  - Parses WebVTT cues and loads roster and meetings/utterances into the database.
- **Verification Tests** in `backend/tests/test_seed.py`:
  - Verified Invariant 6: Every evidence quote in `gold_labels.json` and `gold_labels_heldout.json` is a 100% exact verbatim substring of the raw transcripts.

---

## Task 4: LLM Adapter & Transcript Ingestion Engine
### What Was Built
- **LLM Adapter System** (`backend/app/llm/adapter.py`):
  - `complete_json(prompt_name, variables, schema, model=None, provider=None) -> T`: Generates structured completions validated against Pydantic models.
  - Supported Providers: `fake` (fixture queue and synthesis), `gemini` (Google Gemini API with zero temperature), and `anthropic` (Anthropic Claude API with zero temperature).
  - Modes via `LLM_MODE`: `live` (invokes and caches), `record` (invokes and stores), and `replay` (cache-only; raises `CacheMissError` on miss).
  - Deterministic Disk Caching: Keys calculated as `SHA256(model + rendered_prompt + serialized_inputs)` and stored as JSON under `backend/.llm_cache/`.
  - Schema Validation Retry Loop: Retries up to 2 times upon schema validation or JSON decode failures, feeding the error description back into the prompt.
  - Logging: Records model identifier, request latency in milliseconds, and token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`).
  - Versioned Prompts: Plain text prompt templates stored in `backend/app/llm/prompts/` with `# Version:` headers (`extract_items.v1.txt`, `judge_conflict.v1.txt`).
- **Transcript Ingestion Service** (`backend/app/services/ingestion.py`):
  - Multi-Format Transcript Parsing: Supports `.vtt` (WebVTT), `.srt` (SubRip), `.txt` (timestamped/speaker formatted), and `.json` (structured arrays).
  - Fuzzy Speaker Mapping: Resolves raw speaker names against the roster via exact matching, case-insensitive matching, first-name matching, and initials matching.
  - Flags Unmapped Speakers: Unresolved speakers retain `person_id=None` and trigger a meeting error flag for reviewer attention.
  - Ingestion Orchestration: `ingest_meeting(...)` records parsed utterances and logs audit entries.
  - Speaker Re-mapping: `patch_meeting_speaker(...)` re-maps an unmapped speaker across an entire meeting and updates audit logs.
- **FastAPI Endpoints** (`backend/app/api/routes/meetings.py`):
  - `POST /meetings`: Uploads transcript file, ingests utterances, maps speakers, and sets meeting status.
  - `GET /meetings`: Lists meetings with utterance counts and unmapped speaker flags.
  - `GET /meetings/{id}`: Returns detailed meeting metadata.
  - `GET /meetings/{id}/utterances`: Returns transcript timeline with speaker attribution and unmapped status.
  - `PATCH /meetings/{id}/speakers`: Re-maps a speaker raw identifier to a team member across the meeting.
- **Pytest Suites**:
  - `backend/tests/test_llm.py`: Tests cache hits, replay misses, and schema retry mechanisms.
  - `backend/tests/test_ingestion.py`: Tests all 4 parsing formats, fuzzy speaker matching, unmapped speaker flags, and REST API endpoints.

### How to Run
1. **Run Full Test Suite**:
   ```bash
   make test
   # or
   .venv\Scripts\pytest.exe backend\tests -v
   ```
2. **Start Backend Server**:
   ```bash
   cd backend
   ..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
   ```

### Assumptions Made
- Prompt template files without an explicit file extension fallback to `.v1.txt` or `.txt`.
- Unmapped speakers leave `person_id=None` on the utterance and assign `error="Contains unmapped speaker(s)"` to the meeting until resolved via the PATCH endpoint.

### Open Issues / Deferred
- Extraction pipeline integration (invoking LLM adapter to extract decisions, premises, and actions from ingested meetings) to be implemented in Task 5.
