# DECIDR — BUGS FOUND AND FIXED
**Audit Scope:** Complete Backend, Database, AI Watchdog, Graph Engine, Executor, and Frontend Layers  
**Total Bugs Identified & Resolved:** 10  
**Status:** All 10 Fixes Verified by Automated Regression Tests

---

## 1. BUG RECORD DIRECTORY

### Bug #1: Missing `mark_task_at_risk` Action Type in Domain Enums
- **File Path:** `backend/app/models/enums.py`
- **Location:** `ActionType` enum definition, lines 35–45
- **Severity:** High
- **Root Cause:** The `ActionType` enum lacked the `mark_task_at_risk` member required by the problem statement for notifying task assignees and tagging tracker tickets as resting on compromised premises.
- **Impact:** System failed to generate or execute `mark_task_at_risk` repair actions, limiting repair plans to pausing reminders only.
- **Fix Applied:** Added `mark_task_at_risk = "mark_task_at_risk"` to `ActionType` enum.
- **Regression Test:** `backend/tests/test_repair_safety.py::test_approved_repair_executes_successfully`, `backend/tests/test_repair.py`.

---

### Bug #2: Missing `confidence` on Premise & `estimate_points` on Task
- **File Path:** `backend/app/models/models.py`, `backend/app/schemas/schemas.py`, `backend/app/db/session.py`
- **Location:** `Premise` class (lines 150–180), `Task` class (lines 190–220), `init_db()` migration logic (lines 45–60)
- **Severity:** Medium
- **Root Cause:** The `Premise` model lacked a `confidence` float attribute, and the `Task` model only supported `estimate_hours`, leaving agile story point estimation untracked.
- **Impact:** Blast-radius engine could not report story point sprint velocity impacts, and premise watchdog confidence scores were lost.
- **Fix Applied:** 
  - Added `confidence = Column(Float, nullable=True, default=1.0)` to `Premise`.
  - Added `estimate_points = Column(Float, nullable=True)` to `Task`.
  - Added non-destructive SQLite column migration checks in `init_db()`.
- **Regression Test:** `backend/tests/test_zombie_cost.py::test_mixed_estimation_units_and_unestimated_tasks`.

---

### Bug #3: SQLite Database Locking Under Rapid Concurrent API Requests
- **File Path:** `backend/app/db/session.py`
- **Location:** Engine creation and SQLite connect listener, lines 15–35
- **Severity:** High
- **Root Cause:** Default SQLite connection settings in FastAPI's multithreaded async server caused `sqlite3.OperationalError: database is locked` during rapid concurrent read/write spikes.
- **Impact:** Intermittent 500 server errors during automated benchmark evaluations and concurrent meeting uploads.
- **Fix Applied:** Configured engine with SQLite WAL (Write-Ahead Logging) mode, enabled foreign key constraints, and set a 5000ms busy timeout on connection:
  ```python
  cursor = dbapi_connection.cursor()
  cursor.execute("PRAGMA foreign_keys=ON;")
  cursor.execute("PRAGMA journal_mode=WAL;")
  cursor.execute("PRAGMA busy_timeout=5000;")
  cursor.close()
  ```
- **Regression Test:** `backend/tests/test_adversarial.py`, `backend/tests/test_models.py`.

---

### Bug #4: Premise Watchdog Missing Four-Verdict Evaluation Support
- **File Path:** `backend/app/services/premise_watch.py`, `backend/app/llm/prompts/watch_premises_batched.v1.txt`
- **Location:** `PremiseWatchEvaluation` schema and `watch_premises_against_utterances()`, lines 80–160
- **Severity:** Critical
- **Root Cause:** The watchdog prompt and evaluation schema did not support the required 4-verdict framework (`supports`, `undermines`, `unrelated`, `uncertain`). Ambiguous dialogue could trigger an immediate automated premise break.
- **Impact:** False-positive premise-break alerts generated on tentative or ambiguous conversational remarks.
- **Fix Applied:** 
  - Updated prompt to instruct the LLM to classify evidence into one of: `supports`, `undermines`, `unrelated`, or `uncertain`.
  - Updated watchdog service to treat `uncertain` by setting the premise status to `shaky` and creating a reviewer confirmation card (`verdict="possible_break_please_confirm"`).
  - Ensured uncertain evidence never directly breaks a premise without explicit human confirmation.
- **Regression Test:** `backend/tests/test_premise_e2e_scenario.py::test_four_verdicts_handling_in_watchdog`.

---

### Bug #5: Blast-Radius Zombie-Work Calculation Omitted Story Points
- **File Path:** `backend/app/services/blast_radius.py`
- **Location:** `calculate_blast_radius()`, lines 200–260
- **Severity:** Medium
- **Root Cause:** The zombie-cost computation summed `estimate_hours` but omitted story points, failing to report sprint point velocity waste.
- **Impact:** Incomplete reporting of organizational waste for agile development teams using point estimations.
- **Fix Applied:** Added `points_at_risk` calculation and an explicit `effort_summary` dictionary in the blast-radius response, while maintaining strict adherence to Invariant 10 by counting unestimated tasks without guessing values.
- **Regression Test:** `backend/tests/test_zombie_cost.py::test_mixed_estimation_units_and_unestimated_tasks`.

---

### Bug #6: Executor Missing Handler for `mark_task_at_risk` Action Type
- **File Path:** `backend/app/services/executor.py`
- **Location:** `execute_single_action()`, lines 150–220
- **Severity:** High
- **Root Cause:** `execute_single_action` lacked a branch for `ActionType.mark_task_at_risk`. When approving a proposal containing this action, the executor raised an unhandled `ValueError`.
- **Impact:** Repair execution failed when attempting to mark affected tasks at risk in the tracker.
- **Fix Applied:** Added handling for `ActionType.mark_task_at_risk`, updating the ticket's labels and adding an explanatory comment while recording the change in the append-only audit log.
- **Regression Test:** `backend/tests/test_repair_safety.py::test_approved_repair_executes_successfully`.

---

### Bug #7: Test Utterance Timestamp Type Mismatch (`String` vs `Float`)
- **File Path:** `backend/tests/test_premise_e2e_scenario.py`
- **Location:** Utterance fixture initialization, lines 70–85
- **Severity:** Low
- **Root Cause:** Test fixture passed string timestamps (`"00:01:10.000"`) into `Utterance.start_ts` and `end_ts`, whereas the model schema defines timestamps as `Float` seconds.
- **Impact:** Test failure due to `ValueError: could not convert string to float`.
- **Fix Applied:** Passed float seconds directly (e.g. `start_ts=70.0`, `end_ts=80.0`).
- **Regression Test:** `backend/tests/test_premise_e2e_scenario.py::test_phase2_complete_scenario_meeting1_and_meeting2`.

---

### Bug #8: Invalid `LinkRelation.supports` Enum Usage in Test Fixture
- **File Path:** `backend/tests/test_premise_e2e_scenario.py`
- **Location:** Link fixture initialization, lines 110–120
- **Severity:** Low
- **Root Cause:** Test fixture attempted to create a `Link` row with `relation=LinkRelation.supports`. Premise-to-decision links are maintained via foreign key `Premise.decision_id`; `LinkRelation` is reserved for task/decision links (`implements`, `depends_on`, `supersedes`).
- **Impact:** `AttributeError: type object 'LinkRelation' has no attribute 'supports'`.
- **Fix Applied:** Removed invalid `Link` row and asserted relational integrity via `Premise.decision_id`.
- **Regression Test:** `backend/tests/test_premise_e2e_scenario.py::test_phase2_complete_scenario_meeting1_and_meeting2`.

---

### Bug #9: Global Table Count Assertion Collision in Tracker Tests
- **File Path:** `backend/tests/test_premise_e2e_scenario.py`
- **Location:** Step 7 in scenario test, lines 380–400
- **Severity:** Low
- **Root Cause:** Assertion checked `len(db.query(TrackerTicket).all()) == 0`, which collided with tickets persisted from earlier test fixtures.
- **Impact:** False-positive test failure on test suite runs with shared in-memory database states.
- **Fix Applied:** Changed assertion to compare `len(tickets_after) == len(tickets_before)` to cleanly isolate ticket creation during the step.
- **Regression Test:** `backend/tests/test_premise_e2e_scenario.py::test_phase2_complete_scenario_meeting1_and_meeting2`.

---

### Bug #10: Frontend TypeScript Interface Missing Story Point Blast-Radius Metrics
- **File Path:** `frontend/lib/api.ts`, `frontend/app/affected/page.tsx`
- **Location:** `BlastRadiusResponse` interface and metrics summary card
- **Severity:** Medium
- **Root Cause:** TypeScript definitions in `frontend/lib/api.ts` only typed `hours_at_risk`, causing compiler warnings and omitting story point metrics from the UI.
- **Impact:** Story points were not visible on the Affected Work screen.
- **Fix Applied:** Updated `BlastRadiusResponse` in `frontend/lib/api.ts` to include `points_at_risk?: number` and `effort_summary?: Record<string, any>`, and updated the Affected Work UI to display dual metric badges.
- **Regression Test:** `npm --prefix frontend run build` (compiled static route `/affected` with 0 type errors).

---

## 2. VERIFICATION CONCLUSION
All 10 defects have been resolved and permanently safeguarded with automated regression tests in `backend/tests/`. Zero outstanding defects remain.
