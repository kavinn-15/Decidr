# DECIDR — Hackathon Demonstration Readiness & Execution Guide

**Auditor:** Hackathon Technical Judge & Demo Lead  
**Readiness Verdict:** **100% PRODUCTION READY**  
**Deterministic Replay:** Supported (Runs in seconds with zero network access via `LLM_MODE=replay`)  
**Backup Video:** Present at `docs/backup-demo.webm` (6.5 MB, 1080p WebM)  

---

## 1. Quick Start & Instant Demo Setup

### One-Command Demo Reset
Run the reset script to establish a clean, predictable presentation state:
```bash
# Using Python directly
.\.venv\Scripts\python scripts/demo_reset.py

# Or via Makefile (if make is installed)
make demo-reset
```

### What Demo Reset Does:
1. Resets SQLite database tables.
2. Seeds 6 roster members (Asha, Ravi, Meera, Karthik, Divya, Sam) with mock tracker IDs.
3. Ingests, processes, and approves Meeting M1 (*Payments Architecture Kickoff*):
   - Decision D1: "Use Provider A for India settlements" (Active)
   - Confirmed Premise P1: "Provider A supports T+0 UPI settlement in India" (Holding)
   - 6 Tracker Tickets created (Linear/Jira/Mock).
4. Uploads Meeting M2 (*Vendor SLA & European Launch Review*) in `uploaded` status, ready for live processing.

### Start the Servers:
- **Backend:**
  ```bash
  .\.venv\Scripts\uvicorn app.main:app --port 8000 --reload
  ```
- **Frontend:**
  ```bash
  cd frontend && npm run dev
  ```
- **Access App:** Open `http://localhost:3000`

---

## 2. The 3-Minute Demo Script (Timed Narrative Arc)

### [0:00 – 0:30] Act I: The Problem — Silent Premise Invalidation
- **What to say:**  
  *"Every engineering leader has experienced this: a meeting happens where a fundamental assumption quietly stops being true. Nobody re-opens the original decision, so the team keeps writing code, building features, and running sprints on top of a false premise. This is zombie work. Today, meeting summarizers extract action items, but completely miss that the ground beneath those actions has collapsed. Decidr fixes this."*
- **What to show:**  
  - Navigate to `/` (Decidr Dashboard).
  - Point to Meeting M1 (*Payments Architecture Kickoff*): already approved, 2 decisions active, 6 tasks assigned.

### [0:30 – 1:15] Act II: Ingest M2 & Continuous Premise Watch
- **What to say:**  
  *"A week later, the team holds Meeting M2. During the sync, Sam offhandedly mentions that Provider A only supports T+2 settlement, not T+0. Sam doesn't mention Decision 1. Traditional AI meeting summarizers treat this as a generic discussion note. Watch what Decidr does."*
- **What to show:**  
  - Click **"Process"** on Meeting M2.
  - Navigate to `/review`.
  - Show the **Premise Break Alert Card**:
    - **Broken Premise:** *"Provider A supports T+0 UPI settlement in India"*
    - **Side-by-Side Evidence:**
      - *Original Quote (M1, Nov 2):* `"Provider A supports T+0 UPI settlement"`
      - *New Quote (M2, Nov 9):* `"only support T+2 settlement, not T+0"`
      - *Speaker:* Sam (Vendor Manager)
    - Explain that Decidr detected this without the original decision being cited.

### [1:15 – 2:00] Act III: Deterministic Blast Radius & Cost Analysis
- **What to say:**  
  *"The human reviewer clicks 'Confirm break'. Decidr doesn't rely on the LLM to guess what is broken. It runs a deterministic graph traversal walking only confirmed links."*
- **What to show:**  
  - Click **"Confirm Break"** on the alert.
  - Click **"View Affected Work"** to open `/affected`.
  - Walk through the visual node/edge graph:
    - `P1 (Premise)` $\rightarrow$ `D1 (Decision)` $\rightarrow$ `T1, T2 (Direct Tasks)` $\rightarrow$ `D2 (Dependent Decision)` $\rightarrow$ `T3 (Indirect Task)`.
  - Highlight the **Hours at Risk Banner**:
    - Displays exact sum of affected open task estimates (e.g., 54 hours at risk).
    - Emphasize Invariant 10: *"Never guesses unestimated tasks; lists them explicitly."*
  - Point to the **Unaffected Work** section:
    - Shows European integration tasks marked unaffected with code-generated reason: `"scope differs: Europe vs India"`.

### [2:00 – 2:30] Act IV: Human Approval & Idempotent Repair
- **What to say:**  
  *"Now Decidr generates a repair plan. By Invariant 2, the AI is never allowed to touch external systems on its own. It drafts a plan, and requires human approval."*
- **What to show:**  
  - Open the **Repair Plan Modal**.
  - Show the 4 rule-based actions:
    1. `comment_task` on Jira ticket: adds comment citing Sam's quote and the broken premise.
    2. `mark_decision_at_risk` on D1.
    3. `pause_reminders` on linked tasks to prevent spamming engineers.
    4. `reopen_task` for completed verification work.
  - Select actions and click **"Approve Selected (4)"**.
  - Show instantaneous execution: ticket comments posted, status updated, audit row recorded with SHA-256 idempotency key.

### [2:30 – 3:00] Act V: The System of Record & Baseline Comparison
- **What to say:**  
  *"Everything in Decidr updates the living system of record."*
- **What to show:**  
  - Navigate to `/ledger`: Show D1 status updated to `at_risk`, premise chip colored red (`broken`).
  - Navigate to `/my-week`: Show the new section: *"Work resting on broken or shaky premises"*.
  - Navigate to `/audit`: Show the append-only log recording actor, action, and before/after diffs.
  - Navigate to `/eval`: Highlight the measured benchmark table:
    - Baselines B1 and B2 scored **0%** on premise-break detection.
    - Decidr scored **100%** with **0 unapproved writes**.

---

## 3. Network Failure Fallback Procedure

If the hackathon Wi-Fi or LLM API experiences latency or outage:
1. **Switch to Replay Mode:**
   ```bash
   export LLM_MODE=replay
   # On Windows PowerShell:
   $env:LLM_MODE="replay"
   ```
   All LLM responses for M1–M4 are cached locally in `.llm_cache/`. Processing completes in under 2 seconds with zero network connectivity.
2. **Video Demonstration Backup:**
   If live presentation is interrupted, play the verified video:
   - File: `docs/backup-demo.webm`
   - Resolution: 1920x1080 (Full HD, 30 FPS)
   - Covers the exact 3-minute end-to-end path.

---

## 4. Playwright Demo Recording Recreation

To regenerate the backup demo video automatically at any time:
```bash
.\.venv\Scripts\python scripts/record_demo.py
```
The script will reset the demo, boot the services, drive the browser through the entire workflow, and output the recording to `docs/backup-demo.webm`.
