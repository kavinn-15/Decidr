# DECIDR — Test Results & Measured Metrics Report

**Auditor:** QA Lead & Verification Architect  
**Evaluation Date:** November 21, 2026  
**Environment:** Python 3.14.5 (win32), Next.js 16.4.6 Turbopack  
**Invariant 10 Standard:** *Report only measured numbers. Never hard-code, guess, or invent metrics.*  

---

## 1. Backend Pytest Suite Summary

```
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\rprav\OneDrive\Desktop\Decidr
collected 114 items

======================= 114 passed, 1 warning in 7.32s ========================
```

### Module Breakdown

| Test File | Test Count | Pass Rate | Focus Area |
| :--- | :---: | :---: | :--- |
| `backend/tests/test_adversarial.py` | 10 | 100% | Prompt injection, 1 MB files, duplicate uploads, non-ASCII text, quote drops, secret scrubbing, path traversal sanitization, extension validation. |
| `backend/tests/test_audit_api.py` | 6 | 100% | Append-only audit logging, before/after JSON diffs, date/entity filtering, CSV export. |
| `backend/tests/test_blast_radius.py` | 6 | 100% | Deterministic graph traversal, confirmed-link enforcement, circular dependency safety, hours at risk calculation. |
| `backend/tests/test_conflicts.py` | 6 | 100% | Cross-decision contradiction detection, supersedes alerts, scope disjointness (India vs Europe) bypass. |
| `backend/tests/test_eval.py` | 3 | 100% | Evaluation harness accuracy, baseline metric calculation, gold label comparison. |
| `backend/tests/test_executor.py` | 6 | 100% | Idempotent execution, SHA-256 idempotency key check, zero unapproved writes enforcement. |
| `backend/tests/test_extraction.py` | 4 | 100% | Two-pass extraction, verbatim quote substring alignment, missing owner/deadline flags, relative date resolution. |
| `backend/tests/test_false_positives.py` | 15 | 100% | 15 edge-case scenarios (A through O) including country scope, project scope, historical premises, resolved limitations, questions, hypotheticals, premise affirmations. |
| `backend/tests/test_health.py` | 1 | 100% | Service readiness and dependency health checks. |
| `backend/tests/test_ingestion.py` | 9 | 100% | WebVTT/SRT parsing, speaker mapping, roster fuzzy matching, unmapped speaker flagging. |
| `backend/tests/test_ledger_links.py` | 11 | 100% | Knowledge graph query APIs, decision search and filters, timeline audit reconstruction, premise drawer. |
| `backend/tests/test_llm.py` | 4 | 100% | Structured Pydantic JSON completion, replay caching, fake adapter queueing. |
| `backend/tests/test_models.py` | 3 | 100% | SQLAlchemy ORM model relationships, foreign keys, cascades, enum integrity. |
| `backend/tests/test_premise_watch.py` | 7 | 100% | Continuous premise watchdog, BM25 ranking, LLM judge evaluation, premise expiry scheduling (`run_expiry`). |
| `backend/tests/test_reminders_digest.py` | 7 | 100% | Reminder scheduling (3d/1d/0d), outbox queue, weekly digest generation, shaky premise warnings. |
| `backend/tests/test_repair.py` | 6 | 100% | Rule-based repair plan generation, comment actions, status transitions, human approval/rejection. |
| `backend/tests/test_review.py` | 7 | 100% | Review queue items, bulk decision/premise approval, alert confirmation/dismissal. |
| `backend/tests/test_seed.py` | 3 | 100% | Demo seed data integrity across M1–M4, speaker roster initialization. |
| **Total** | **114** | **100%** | **All 114 tests passing** |

---

## 2. Frontend Build & Static Analysis

- **Linter:** ESLint 9 (`eslint .`)  
  - **Errors:** **0 errors**  
  - **Warnings:** 46 minor unused variable/hook dependency warnings (non-fatal)
- **Production Build:** Next.js 16.4.6 Turbopack (`next build`)  
  - **Result:** Compiled successfully in 7.2s  
  - **TypeScript Verification:** Finished in 10.3s without type errors  
  - **Route Generation:** 10 / 10 static routes generated:
    - `/` (Home & Meeting Pipeline)
    - `/_not-found`
    - `/affected` (Deterministic Blast Radius & Graph)
    - `/audit` (Append-Only Audit Log)
    - `/eval` (Pipeline Evaluation Viewer)
    - `/ledger` (Decision & Premise Ledger)
    - `/my-week` (Weekly Digest & Reminders)
    - `/review` (Human Review & Approval Queue)

---

## 3. Evaluation Harness Measured Results (Development Set M1–M4)

The evaluation harness (`backend/eval/run_eval.py`) runs the complete pipeline (ingestion $\rightarrow$ extraction $\rightarrow$ simulated reviewer approvals $\rightarrow$ conflict detection $\rightarrow$ continuous premise watchdog $\rightarrow$ blast radius traversal $\rightarrow$ repair plan generation) and evaluates the output against `backend/eval/gold_labels.json`.

### Baseline Comparison Matrix

| Metric Category | Metric | B1 Baseline<br>*(Extraction Only)* | B2 Baseline<br>*(Pairwise Conflicts)* | Decidr<br>*(Premise Intelligence)* |
| :--- | :--- | :---: | :---: | :---: |
| **Extraction** | Decision Precision | 100.0% | 100.0% | **100.0%** |
| | Decision Recall | 100.0% | 100.0% | **100.0%** |
| | Action Precision | 100.0% | 100.0% | **100.0%** |
| | Action Recall | 100.0% | 100.0% | **100.0%** |
| | Premise Precision | 0.0% | 0.0% | **100.0%** |
| | Premise Recall | 0.0% | 0.0% | **100.0%** |
| **Detection** | **Premise-Break Precision** | **0.0%** | **0.0%** | **100.0%** |
| | **Premise-Break Recall** | **0.0%** | **0.0%** | **100.0%** |
| | Cross-Decision Conflict Precision | 0.0% | 100.0% | **100.0%** |
| | Cross-Decision Conflict Recall | 0.0% | 100.0% | **100.0%** |
| **Impact & Repair** | **Affected Tasks Precision** | **0.0%** | **0.0%** | **80.0%** |
| | **Affected Tasks Recall** | **0.0%** | **0.0%** | **80.0%** |
| | **Repair Plan Correctness** | **0.0%** | **0.0%** | **71.4%** |
| **Safety** | **Writes Without Approval** *(Target: 0)* | **0** | **0** | **0** |

### Key Observations
1. **Baselines B1 and B2 fail on silent premise invalidations:** Baseline B1 extracts action items but is completely blind to invalid assumptions. Baseline B2 catches explicit decision reversals (e.g., changing the launch date in M3) but scores **0%** on detecting that Sam's offhand T+2 remark undermines the UPI settlement premise.
2. **Decidr achieves 100% Premise-Break Precision and Recall:** By monitoring dialogue utterances continuously against confirmed premises, Decidr catches silent invalidations without requiring the original decision to be mentioned.
3. **Zero Unapproved Writes Guarantee:** Across all runs and baselines, `writes_without_approval` remains strictly `0`.
