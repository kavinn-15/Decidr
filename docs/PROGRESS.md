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
│   └── reset_db.py
├── backend/
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
│   │   │   └── prompts/
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── audit.py
│   │   └── api/
│   │       ├── __init__.py
│   │       └── routes/
│   │           └── __init__.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   └── test_models.py
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
- Settings configuration using `pydantic-settings` reading `.env` with all specified defaults and variables (`DATABASE_URL`, `LLM_PROVIDER`, `LLM_MODE`, `LLM_MODEL`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `GITHUB_REPO`, `TRACKER`, SMTP settings, `DEMO_MODE`).
- CORS middleware configured for `http://localhost:3000`.
- Pytest testing setup with initial health check test.
- LLM Adapter architecture in `backend/app/llm/adapter.py` caching responses deterministically on disk keyed by `hash(model, prompt, input)`.
- Frontend Next.js App Router application with Tailwind CSS and Lucide icons.
- Left sidebar layout navigation across all six routes:
  - `/` (Meetings)
  - `/review` (Review Queue)
  - `/affected` (Decision Impact & Affected Work)
  - `/ledger` (Decision Ledger)
  - `/my-week` (My Week)
  - `/audit` (Audit Log)
- Typed API client in `frontend/lib/api.ts` accessing `NEXT_PUBLIC_API_URL`.
- Root configuration: `Makefile` (`dev`, `test`, `seed`, `reset`, `eval`), `.env.example`, `.gitignore`, initialized git repository.

---

## Task 2: Data Models, Schemas & Append-Only Audit Log
### What Was Built
- **SQLAlchemy 2.0 ORM Models** for all 15 entities (`backend/app/models/models.py`):
  1. `people`: `id`, `name`, `email` (unique index), `tracker_id`, `slack_id` (nullable)
  2. `meetings`: `id`, `title`, `date`, `project`, `region`, `release`, `transcript_ref`, `status` (`uploaded`, `processing`, `review`, `done`, `failed`), `error`
  3. `utterances`: `id`, `meeting_id` (FK), `idx`, `speaker_raw`, `person_id` (FK nullable), `text`, `start_ts`
  4. `items`: `id`, `meeting_id` (FK), `type` (`decision`, `action`), `text`, `owner_id` (FK nullable), `deadline`, `needs_owner`, `needs_deadline`, `confidence`, `evidence_quote`, `utterance_id` (FK nullable), `review_state` (`proposed`, `approved`, `edited`, `rejected`)
  5. `decisions`: `id`, `item_id` (FK), `text`, `scope_project`, `scope_region`, `scope_release`, `effective_from`, `effective_to`, `status` (`active`, `superseded`, `at_risk`), `version`, `supersedes_id` (FK nullable), `embedding`
  6. `decision_versions`: `id`, `decision_id` (FK), `version`, `text`, `changed_at`, `changed_by`
  7. `premises`: `id`, `decision_id` (FK), `text`, `evidence_quote`, `utterance_id` (FK nullable), `scope_project`, `scope_region`, `valid_from`, `valid_until`, `state` (`proposed`, `confirmed`, `rejected`), `status` (`holding`, `shaky`, `broken`, `expired`), `confirmed_by`
  8. `links`: `id`, `source_type`, `source_id`, `target_type`, `target_id`, `relation` (`implements`, `depends_on`, `supersedes`), `confirmed`, `confidence`, `rationale`
  9. `tasks`: `id`, `item_id` (FK), `decision_id` (FK nullable), `title`, `description`, `owner_id` (FK nullable), `due_date`, `estimate_hours`, `provisional`, `status` (`open`, `at_risk`, `done`, `cancelled`), `tracker_ref`, `tracker_url`
  10. `alerts`: `id`, `kind` (`conflict`, `premise_break`, `expiry`), `meeting_id` (FK nullable), `utterance_id` (FK nullable), `premise_id` (FK nullable), `decision_id` (FK nullable), `verdict`, `old_quote`, `new_quote`, `explanation`, `state` (`open`, `confirmed`, `dismissed`), `proposal_id` (FK nullable)
  11. `change_proposals`: `id`, `trigger_type`, `trigger_id`, `summary`, `state` (`draft`, `approved`, `rejected`, `executed`), `created_at`, `decided_by`, `decided_at`
  12. `change_actions`: `id`, `proposal_id` (FK), `action_type` (`mark_decision_at_risk`, `comment_task`, `reopen_task`, `create_task`, `pause_reminders`, `cancel_task`), `target_type`, `target_id`, `payload` (JSON), `idempotency_key` (UNIQUE), `state` (`draft`, `approved`, `rejected`, `executed`, `failed`), `executed_at`, `result` (JSON)
  13. `reminders`: `id`, `task_id` (FK), `kind` (`3d`, `1d`, `morning`), `due_at`, `state` (`pending`, `sent`, `paused`, `skipped`), `channel` (`email`, `slack`), `pause_reason`
  14. `outbox`: `id`, `channel`, `to_addr`, `subject`, `body`, `created_at`, `sent`
  15. `audit_log`: `id`, `actor`, `action`, `entity_type`, `entity_id`, `before` (JSON nullable), `after` (JSON nullable), `created_at`
- **String Enums** for every state and relation field (`backend/app/models/enums.py`).
- **SQLite Foreign Key Enforcement**: Enabled via SQLAlchemy engine `connect` event listener (`PRAGMA foreign_keys=ON;`).
- **Append-Only Audit Log**: Strict event listeners on `AuditLog` (`before_update`, `before_delete`) and `Session` (`before_flush`, `do_orm_execute`) that raise `ReadOnlyAuditLogError` on any update or delete operation (Invariant 7).
- **Audit Service** in `backend/app/services/audit.py` implementing `log(actor, action, entity_type, entity_id, before, after, db=None)`.
- **Pydantic v2 Schemas** in `backend/app/schemas/schemas.py` providing typed Base, Create, and Read schemas for all 15 models.
- **Database Reset Scripts** (`scripts/reset_db.py`, `scripts/reset-db`, `scripts/reset-db.bat`).
- **Unit and Integration Tests** (`backend/tests/test_models.py`):
  - Chain creation verification: `meeting > utterance > item > decision > premise > task > links`
  - Foreign key constraint enforcement assertions
  - Audit log append-only immutability tests (instance updates, deletes, and bulk operations all verified to raise `ReadOnlyAuditLogError`)

### How to Run
1. **Run Pytest Suite**:
   ```bash
   .venv\Scripts\pytest.exe backend\tests -v
   ```
2. **Reset and Initialize Database**:
   ```bash
   python scripts/reset_db.py
   # Or using Makefile
   make reset
   ```
3. **Run Backend Service**:
   ```bash
   cd backend
   ..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
   ```
4. **Run Frontend Application**:
   ```bash
   cd frontend
   npm run dev
   ```

### Assumptions Made
- In SQLite, foreign key constraints must be explicitly enabled on every DBAPI connection using `PRAGMA foreign_keys=ON;`.
- Links support polymorphic relationships (`source_type`, `source_id`, `target_type`, `target_id`) to accommodate decision-to-decision, task-to-decision, and task-to-task dependencies.
- Audit log is strictly append-only; attempts to modify or delete audit rows raise a custom `ReadOnlyAuditLogError` exception before touching the database.

### Open Issues / Deferred
- LLM adapter providers (live Anthropic/Gemini) to be plugged in during later extraction & conflict judging tasks.
- Background reminder cron/scheduler integration with APScheduler to be wired with the `reminders` table in later phases.
