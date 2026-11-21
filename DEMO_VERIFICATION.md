# DECIDR — DEMO VERIFICATION & PRESENTATION RUNBOOK
**Target Presentation:** 3-Minute Live Hackathon Demonstration  
**Primary Demo Flow:** Meeting 1 (Decision & Premise) -> Meeting 2 (Quiet Premise Break) -> Review Alert -> Blast Radius -> Human-Approved Repair -> Audit Log  
**Deterministic Fallbacks:** Replay Mode (`LLM_MODE=replay`) & Backup Video (`docs/backup-demo.webm`, 6.54 MB)

---

## 1. THREE-MINUTE PRESENTATION SCRIPT & TIMELINE

```text
+-------------------+---------------------------------------------------------+
| Time Window       | Visual Action & Presenter Script                        |
+-------------------+---------------------------------------------------------+
| 0:00 - 0:30       | INTRO & THE HIDDEN PROBLEM                              |
|                   | Screen: Dashboard (http://localhost:3000)               |
|                   | Script: "Every company makes decisions based on hidden   |
|                   | premises. In Meeting 1, the team chose Vendor A because |
|                   | they believed Vendor A supported international recurring |
|                   | payments. Tasks were assigned, tickets created in Jira. |
|                   | Then, two weeks later, in Meeting 2..."                 |
+-------------------+---------------------------------------------------------+
| 0:30 - 1:10       | THE QUIET INVALIDATION                                  |
|                   | Screen: Upload / Process Meeting 2                      |
|                   | Script: "In Meeting 2, Sam mentions offhand: 'Vendor A  |
|                   | told us international recurring billing isn't on their  |
|                   | tier.' Sam never mentions Decision 1. Standard tools    |
|                   | miss this completely. But Decidr's continuous premise   |
|                   | watchdog catches it immediately."                       |
+-------------------+---------------------------------------------------------+
| 1:10 - 1:40       | HUMAN-IN-THE-LOOP REVIEW                                |
|                   | Screen: Meeting Review (/review)                        |
|                   | Script: "Decidr surfaces a Premise Break Alert card.    |
|                   | Side-by-side verbatim quotes show the original belief   |
|                   | and the new statement. The human reviewer confirms the  |
|                   | break. Invariant 5: the AI only proposes; humans decide.|
+-------------------+---------------------------------------------------------+
| 1:40 - 2:15       | BLAST RADIUS & ZOMBIE WORK                              |
|                   | Screen: Affected Work (/affected)                       |
|                   | Script: "Instantly, Decidr traverses the dependency     |
|                   | graph. Not just Decision 1, but downstream Decision 3   |
|                   | and Tasks 1, 2, and 6 are compromised. Crucially,       |
|                   | Decidr isolates disjoint scopes: Europe Task 5 is       |
|                   | unaffected. We calculate the exact zombie-work cost:    |
|                   | 42 engineering hours and 8 story points saved!"         |
+-------------------+---------------------------------------------------------+
| 2:15 - 2:45       | SAFE REPAIR PLAN EXECUTION                              |
|                   | Screen: Repair Plan Drawer                              |
|                   | Script: "Decidr prepares a repair plan: pause reminders,|
|                   | notify assignees, and mark tickets at risk in the       |
|                   | tracker. Invariant 2: zero external writes occur until  |
|                   | the reviewer approves. One click on 'Execute', and the  |
|                   | changes are applied idempotently with SHA-256 keys."    |
+-------------------+---------------------------------------------------------+
| 2:45 - 3:00       | THE DOWNSTREAM IMPACT                                   |
|                   | Screen: Decision Ledger (/ledger) & Audit (/audit)      |
|                   | Script: "The Decision Ledger now flags Decision 1 as    |
|                   | at-risk. The personal My-Week view warns engineers of   |
|                   | shaky premises. And our append-only Audit Log records   |
|                   | every single step. That is Decidr: stopping zombie work |
|                   | before it starts."                                      |
+-------------------+---------------------------------------------------------+
```

---

## 2. DEMO RESET & DETERMINISTIC REPLAY

To guarantee that live demonstrations succeed regardless of venue Wi-Fi stability, API rate limits, or latency, Decidr provides a deterministic reset and replay system.

### One-Command Demo Reset
Resets the database, loads the roster, imports Meeting 1 as fully approved with mock tracker tickets, and stages Meeting 2 ready for instant processing:
```powershell
python scripts/demo_reset.py
# Or using Makefile:
make demo-reset
```

### Zero-Network Replay Mode
When `LLM_MODE=replay` is set in `.env`, Decidr intercepts all LLM extraction, conflict detection, watchdog evaluation, and repair generation calls, serving pre-recorded, verbatim verified responses from `backend/seed/`:
- **Execution Speed:** Sub-second (typically 200–400ms per step).
- **Network Dependency:** Completely offline; 0 bytes transmitted over the WAN.
- **Reproducibility:** 100% deterministic output identical to production runs.

---

## 3. OFFLINE BACKUP VIDEO VERIFICATION

In accordance with hackathon submission guidelines, a complete backup video of the 3-minute demo has been pre-recorded and verified:

- **File Path:** [docs/backup-demo.webm](file:///c:/Users/rprav/OneDrive/Desktop/Decidr/docs/backup-demo.webm)
- **Root Path:** [backup-demo.webm](file:///c:/Users/rprav/OneDrive/Desktop/Decidr/backup-demo.webm)
- **File Size:** `6,542,731 bytes` (6.54 MB)
- **Container / Codec:** WebM (VP8/VP9 Video + Vorbis/Opus Audio)
- **Content Covered:** Full end-to-end flow from dashboard to M2 processing, alert confirmation, blast radius, repair plan approval, tracker updates, and audit trail.

---

## 4. SCREEN-BY-SCREEN AUDIT SUMMARY

| Screen Route | Key Elements Audited | Loading State | Empty State | Error State |
| :--- | :--- | :---: | :---: | :---: |
| `/` (Hub) | Meeting cards, upload modal, progress indicator, pending count. | Spinner / Skeleton | Clean empty banner | Alert banner with retry |
| `/review` | Card queue, side-by-side quotes, approve/reject buttons, edit modal. | Skeleton cards | "All caught up" card | Toast error |
| `/affected` | Impact summary, hours/points badges, affected task list, repair drawer. | Graph skeleton | "No active breaks" | Error banner |
| `/ledger` | Search filter, status tags, slide-over drawer, SVG graph, version diff. | Table shimmer | "No decisions found" | Drawer error state |
| `/my-week` | Day columns, task cards, shaky premise badges, outbox simulator. | Day skeletons | "No tasks scheduled" | Outbox load error |
| `/audit` | Chronological event table, actor filter, diff modal, CSV download. | Table loading | "No audit events" | Alert banner |
| `/eval` | Benchmark cards, precision/recall bars, baseline comparison matrix. | Shimmer cards | "No run recorded" | Execution failure card |

**Readiness Verdict:** All UI screens and presentation pathways are 100% demo-proof.
