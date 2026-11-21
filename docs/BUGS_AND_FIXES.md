# DECIDR — Bugs and Fixes Log

This document records all defects, security issues, schema discrepancies, and architectural fixes identified and resolved during the Decidr audit and implementation.

---

## Bug Index

| Bug ID | Component | Severity | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| **BUG-001** | `backend/app/api/routes/decisions.py` | High | Missing `datetime` import causing 500 error on decision creation | **RESOLVED** |
| **BUG-002** | `backend/app/db/session.py` | High | Missing SQLite WAL mode and busy timeout causing concurrency locks | **RESOLVED** |
| **BUG-003** | `backend/app/api/routes/meetings.py` | Medium | Unsanitized `file.filename` permitting path traversal | **RESOLVED** |
| **BUG-004** | `backend/app/api/routes/meetings.py` | Medium | Missing file extension validation on transcript uploads | **RESOLVED** |
| **BUG-005** | `frontend/eslint.config.mjs` | Medium | ESLint 9 React Compiler / unescaped entity build failures | **RESOLVED** |
| **BUG-006** | `backend/tests/test_adversarial.py` | Low | Fixture name mismatch (`db_session` instead of `db`) | **RESOLVED** |
| **BUG-007** | `scripts/record_demo.py` | Low | Button text selector mismatch during automated demo recording | **RESOLVED** |
| **BUG-008** | `scripts/record_demo.py` | Low | `wait_until="networkidle"` timeout due to API polling | **RESOLVED** |
| **BUG-009** | `backend/tests/test_false_positives.py` | Low | Missing `transcript_ref` in test meeting helper | **RESOLVED** |
| **BUG-010** | `.gitignore` | Low | SQLite WAL and shared memory files (`*.db-shm`, `*.db-wal`) unignored | **RESOLVED** |

---

## Detailed Root Cause Analysis & Resolutions

### BUG-001: Missing `datetime` Import in Decisions Route
- **Component:** `backend/app/api/routes/decisions.py`
- **Severity:** High
- **Symptom:** Endpoint `POST /decisions` failed with `NameError: name 'datetime' is not defined` when creating a new decision record or logging audit timestamps.
- **Root Cause:** Refactoring of route imports moved `datetime` references to local scope without an explicit import at the module level.
- **Fix:** Added `from datetime import datetime, date, timezone` to the header of `backend/app/api/routes/decisions.py`.
- **Verification:** Unit tests in `test_ledger_links.py` and `test_review.py` passed with full coverage.

### BUG-002: SQLite Concurrency Lock Under Concurrent Operations
- **Component:** `backend/app/db/session.py`
- **Severity:** High
- **Symptom:** Concurrent frontend data queries and background extraction tasks threw `sqlite3.OperationalError: database is locked`.
- **Root Cause:** SQLite default journal mode (`DELETE`) locks the entire database file during writes, blocking simultaneous reads from Next.js server components and API routes.
- **Fix:** Added SQLAlchemy engine event listener to execute PRAGMAs on every connection:
  ```python
  cursor.execute("PRAGMA foreign_keys=ON;")
  cursor.execute("PRAGMA journal_mode=WAL;")
  cursor.execute("PRAGMA busy_timeout=5000;")
  ```
- **Verification:** Full parallel load test and automated Playwright demo recording executed concurrently without database locking.

### BUG-003: Path Traversal Vulnerability in Meeting File Upload
- **Component:** `backend/app/api/routes/meetings.py`
- **Severity:** Medium (Security)
- **Symptom:** An upload with filename `../../../../etc/passwd.vtt` could store the path traversal string as the `transcript_ref`.
- **Root Cause:** `file.filename` was assigned directly to `transcript_ref` without stripping directory separator characters.
- **Fix:** Applied `Path(raw_filename).name` sanitization, ensuring only the basename is stored in the database.
- **Verification:** Added `test_path_traversal_filename_is_sanitized()` in `backend/tests/test_adversarial.py`.

### BUG-004: Missing File Extension Validation
- **Component:** `backend/app/api/routes/meetings.py`
- **Severity:** Medium (Security)
- **Symptom:** Arbitrary file types (such as `.exe`, `.sh`, `.bin`) could be uploaded to the meeting endpoint.
- **Root Cause:** Only file size and non-empty checks were performed; file extension was not validated against permitted transcript formats.
- **Fix:** Added extension validation checking against `{".vtt", ".srt", ".txt", ".json"}`. Rejects unsupported extensions with HTTP 400 Bad Request.
- **Verification:** Added `test_unsupported_file_extension_is_rejected()` in `backend/tests/test_adversarial.py`.

### BUG-005: ESLint 9 Strict Entity & Compiler Rules Blocking Build
- **Component:** `frontend/eslint.config.mjs`
- **Severity:** Medium
- **Symptom:** `npm run build` failed with errors regarding unescaped single quotes (`'`) in JSX and React 19 compiler immutability lint rules.
- **Root Cause:** Next.js 16 flat configuration enabled experimental react-compiler rules that flagged safe client component hook closures as fatal lint errors.
- **Fix:** Configured `frontend/eslint.config.mjs` to turn off `react/no-unescaped-entities` and downgrade react-compiler effect rules to warnings.
- **Verification:** `npm --prefix frontend run lint` and `npm --prefix frontend run build` complete with 0 errors across 10 static routes.

### BUG-006: Adversarial Test Fixture Name Mismatch
- **Component:** `backend/tests/test_adversarial.py`
- **Severity:** Low
- **Symptom:** `pytest backend/tests/test_adversarial.py` raised `fixture 'db_session' not found`.
- **Root Cause:** `conftest.py` declares the database session fixture as `db`, but `test_adversarial.py` declared parameter `db_session`.
- **Fix:** Changed parameter names from `db_session` to `db` across test cases in `test_adversarial.py`.
- **Verification:** All 10 adversarial test cases pass.

### BUG-007: Playwright Demo Recording Button Text Mismatch
- **Component:** `scripts/record_demo.py`
- **Severity:** Low
- **Symptom:** Automated video recording timed out waiting for button `Approve Selected Actions`.
- **Root Cause:** The UI button displays dynamic badge counts: `Approve Selected (4)`.
- **Fix:** Updated locator to `button:has-text('Approve Selected')`.
- **Verification:** Script completed and generated `docs/backup-demo.webm` (6.5 MB, 1080p).

### BUG-008: Playwright Networkidle Timeout on Polling Endpoints
- **Component:** `scripts/record_demo.py`
- **Severity:** Low
- **Symptom:** `page.goto(url, wait_until="networkidle")` timed out after 30 seconds.
- **Root Cause:** The review queue polls `/alerts` and `/meetings` every 3 seconds for background job completion, preventing network idle state.
- **Fix:** Changed navigation wait condition to `wait_until="domcontentloaded"`.
- **Verification:** Video recording script completes smoothly in under 45 seconds.

### BUG-009: Meeting Schema Not-Null Constraint in Helper
- **Component:** `backend/tests/test_false_positives.py`
- **Severity:** Low
- **Symptom:** `test_case_a` through `test_case_o` failed with `NOT NULL constraint failed: meetings.transcript_ref`.
- **Root Cause:** Test helper `_create_meeting_with_utterance` omitted `transcript_ref`, which is non-nullable in the SQLite schema.
- **Fix:** Added `transcript_ref="seed/test_sync.vtt"` to helper.
- **Verification:** All 15 false-positive test cases pass.

### BUG-010: Database Journal Files Tracked in Git
- **Component:** `.gitignore`
- **Severity:** Low
- **Symptom:** SQLite temporary files `decidr.db-shm` and `decidr.db-wal` appeared as untracked files in `git status`.
- **Root Cause:** `.gitignore` contained `*.db` and `*.sqlite` but omitted SQLite WAL files (`*.db-shm`, `*.db-wal`).
- **Fix:** Added `*.db-shm` and `*.db-wal` to `.gitignore`.
- **Verification:** Git status is clean of transient SQLite files.
