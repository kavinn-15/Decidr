# DECIDR 3-MINUTE DEMO SCRIPT

**Duration:** 3 Minutes  
**Target Scenario:** Vendor settlement premise break in Meeting 2 invalidates multi-hop downstream payment tasks.  
**Audience:** Technical Leadership, Product Engineers, Architecture Reviewers  

---

## Pre-Demo Checklist (10 Seconds)
1. Ensure the demo environment is cleanly reset:
   ```bash
   make demo-reset
   ```
2. Ensure both services are running:
   - Backend API: `http://localhost:8000` (FastAPI)
   - Frontend UI: `http://localhost:3000` (Next.js)
3. Open browser at `http://localhost:3000` in full-screen (1280x800 or 1920x1080).

---

## 3-Minute Presentation Walkthrough

### 0:00 – 0:35: The Problem & Baseline State
- **Screen:** `/` (Meetings Dashboard)
- **What to Say:**
  > "Modern software engineering teams make critical architectural commitments during verbal video meetings. But weeks later, when an external vendor or assumption changes, nobody remembers what rested on that premise—resulting in hundreds of hours of wasted engineering work and broken production releases.
  > 
  > This is **Decidr**: the autonomous ChangeGuard agent that monitors decisions, verifies premises against every utterance, and deterministically halts downstream work when assumptions break.
  > 
  > Here on our Meetings Dashboard, you can see Meeting 1—our Payments Revamp kickoff—is already processed and approved. Real tasks are open in our tracker. Meeting 2 has just been uploaded from this morning's vendor sync."

---

### 0:35 – 1:05: Processing & Continuous Dialogue Watchdog
- **Screen:** `/` -> `/review`
- **Actions:**
  1. Click the **"Process"** button on Meeting 2 (*Vendor SLA & European Launch Review*).
  2. Notice the status badge transition: `uploaded` -> `processing` -> `review` with an alert badge: `1 cards pending`.
  3. Click **"Review Queue"**.
- **What to Say:**
  > "Decidr doesn't just extract decisions; it runs a continuous premise watchdog across **every dialogue utterance**.
  > 
  > Notice what happened: in Meeting 2, the team wasn't even making a decision about India. Sam was just venting about vendor meetings over the weekend. Yet Decidr detected a contradiction against our earlier confirmed premise."

---

### 1:05 – 1:40: Premise Break & Verbatim Evidence Verification
- **Screen:** `/review` (Review Queue)
- **Actions:**
  1. Highlight the top red/amber **Premise Break Alert Card**.
  2. Point out the side-by-side quote layout:
     - **Then:** `"Provider A supports T+0 UPI settlement"`
     - **Now:** `"Provider A told me this morning they only support T+2 settlement, not T+0 for merchant payouts"`
  3. Click on the quote to highlight the exact utterance in the transcript dialogue context.
  4. Click the red **"Confirm Break"** button.
- **What to Say:**
  > "Here is our core novelty: side-by-side evidence quotes verified as exact verbatim substrings to prevent hallucination.
  > 
  > Sam mentioned Provider A only supports T+2 settlement, directly breaking our premise P1 upon which our entire checkout pipeline was budgeted.
  > 
  > I'll click 'Confirm Break'. Notice: under Invariant 2, Decidr doesn't touch external trackers autonomously. It requires human confirmation and records an immutable audit log entry."

---

### 1:40 – 2:20: Deterministic Blast Radius & Hours at Risk
- **Screen:** Click sidebar link **"Affected Work"** (`/affected`)
- **Actions:**
  1. Point out the top **Hours at Risk Banner** (`64.0h`).
  2. Show the **Chain Nodes Visualization** on Task #1:
     `P1 (Premise) -> D1 (Decision) -> T1 (Task)`
  3. Show the multi-hop propagation on Task #6:
     `P1 -> D1 -> D3 -> T6` (Depth 2 indirect dependency).
  4. Expand the unaffected section: show Task #5 (*Provider B for Europe*) is unaffected due to **disjoint geographic scope** (*Europe* vs *India*).
- **What to Say:**
  > "Now look at the blast radius. This graph traversal runs in **plain code with zero LLM hallucinations**.
  > 
  > It walks confirmed dependency links only: Premise P1 impacts Decision 1, which directly invalidates 4 engineering tasks: SDK integration, reconciliation screen, test plan, and finance sign-off.
  > 
  > Even more impressive: it propagates multi-hop! Task 6—launch checklist sign-off—is two links away because it depends on reconciliation gate D3.
  > 
  > Meanwhile, our European evaluation task is safely flagged as unaffected because its scope is disjoint: Europe versus India. We calculate **64 hours of engineering work at immediate risk**."

---

### 2:20 – 2:45: Rule-Based Safe Recovery (Repair Plan Approval)
- **Screen:** Click **"Review Repair Plan"** button
- **Actions:**
  1. Open the Repair Plan modal.
  2. Show generated actions:
     - `mark_decision_at_risk` for D1 and D3
     - `comment_task` with broken quote on affected tracker tickets
     - `pause_reminders` on contract review
  3. Toggle **"Dry Run / Preview"** to show simulated payloads.
  4. Click **"Approve Selected Actions"**.
- **What to Say:**
  > "Rather than letting engineers continue building on obsolete assumptions, Decidr generates a structured repair plan.
  > 
  > It drafts precise actions: marking decisions at risk, commenting on open tracker tickets, and pausing reminder emails.
  > 
  > I review the actions, verify the payload in dry-run mode, and click **Approve Selected Actions**. Only now does the executor touch the external world."

---

### 2:45 – 3:00: Downstream Safety: My Week, Tracker, & Audit Log
- **Screen:**
  1. Click **"My Week"** (`/my-week`): show warning section *"Work resting on broken or shaky premises"*.
  2. Click **"Audit Log"** (`/audit`): show append-only timestamped history of all approvals, transitions, and before/after payloads.
- **What to Say:**
  > "Downstream, every engineer is protected. On the **My Week** screen, engineers see warnings that their tasks rest on broken premises before starting work.
  > 
  > And on our **Audit Log**, corporate security has an immutable, append-only record of every state change, proposal, and human approval.
  > 
  > That is Decidr: verbal meetings transformed into active, self-defending architecture."

---

## Network Failure Fallback Plan (100% Offline Mode)

If live network or external API access fails during a presentation:
1. **Enable Replay Cache:**
   Decidr includes disk-cached responses in `backend/.llm_cache/`.
   In your `.env` file, set:
   ```env
   LLM_MODE=replay
   LLM_PROVIDER=gemini
   ```
2. **Instant Sub-Second Fallback:**
   In replay mode, `complete_json` resolves against SHA-256 keyed cache files locally. Meeting 2 processes in **under 0.5 seconds** with **0 network requests**.
3. **Emergency Reset:**
   Run `make demo-reset` in your terminal. It rebuilds the database in 3 seconds back to the exact initial state.
