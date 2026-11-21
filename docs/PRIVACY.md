# DECIDR PRIVACY & DATA GOVERNANCE POLICY

**Document Version:** 1.0.0  
**Effective Date:** 2026-11-21  
**Target Invariants:** Invariant 2 (Execution Safety & Zero Unapproved Writes), Invariant 3 (Append-Only Audit Log), Invariant 10 (Empirical Integrity)

---

## 1. Executive Summary & Privacy-by-Design

Decidr is an enterprise-grade ChangeGuard platform that analyzes project dialogues, tracks decision premises, and calculates blast-radius impacts across engineering workflows. Decidr adheres to a strict **privacy-by-design** and **data-minimization** architecture:

1. **Zero Raw Audio/Video Storage:** Decidr operates purely on text transcripts (`.vtt`, `.srt`, `.txt`, `.json`); it never stores, transmits, or processes raw audio, video, or biometric streams.
2. **Local Data Sovereignty:** All relational databases, audit logs, and graph linkages reside locally or within customer-controlled private VPCs (`decidr.db`).
3. **No External Writes Without Human Authorization:** No external tracker tickets (GitHub Issues, Jira, Linear) or outbound communications (Slack, SMTP emails) are dispatched without explicit human sign-off in the Review Queue.
4. **Zero-Training LLM Guarantee:** Enterprise API agreements with supported foundation models (Google Gemini API and Anthropic Claude) prohibit the retention or use of customer prompt inputs for public model fine-tuning or training.

---

## 2. Participant Consent & Ingestion Controls

Decidr ingests team conversations to extract operational decisions, premises, and action items.

### 2.1 Explicit Notice and Consent
Organizations deploying Decidr must adhere to applicable two-party or all-party consent recording regulations.
- Ingestion pipelines require recording notification badges during live calls (e.g. Google Meet, Zoom, Microsoft Teams bots).
- Transcripts should only be uploaded from authorized project channels where team members have acknowledged recording policies.

### 2.2 Speaker Roster & Identity Mapping
- Incoming utterances are mapped to enterprise personnel via the configured Roster (`backend/seed/roster.json` or enterprise SCIM directory).
- **Invariant 1 Enforcement (No Hallucinated Owners):** If an utterance speaker cannot be verified against the corporate roster, Decidr flags the speaker as `unmapped`. The system refuses to assign tracker tasks to unverified names until a human reviewer manually patches the speaker identity.

---

## 3. LLM Transmission Boundary: What Leaves Your Perimeter?

Decidr minimizes LLM exposure through deterministic pre-filtering and caching.

### 3.1 What IS Sent to the Model:
- **Two-Pass Extraction:** The text of dialogue blocks (~10–20 utterances per chunk) is sent to extract candidate decisions, premises, and actions.
- **Continuous Watchdog:** Utterances containing 5+ words are evaluated alongside 2 preceding and 2 following dialogue turns to contextualize candidate premise updates.
- **Cross-Decision Conflict Judge:** Decisions sharing overlapping scope (project and region) are evaluated for supersession or contradictions.

### 3.2 What is NEVER Sent to the Model:
- **Disjoint Scope Decisions (Invariant 9):** If two decisions belong to disjoint projects or different geographic regions (e.g. *Europe* vs. *India*), Decidr drops candidate comparison **prior to model invocation**. The LLM is skipped entirely (0 calls, 0 tokens, 0 network bytes).
- **Blast Radius Graph Traversal (Invariants 4 & 5):** Dependency tracing across decisions and downstream tasks is computed **100% in deterministic code (BFS)** with zero LLM calls.
- **Repair Plan Generation:** Action formulation (`mark_decision_at_risk`, `comment_task`, `pause_reminders`, `reopen_task`) is performed by deterministic rule-based algorithms.
- **Credentials & Secrets:** API keys, database credentials, Slack webhook tokens, and SMTP passwords never enter prompt templates.

### 3.3 Replay & Air-Gapped Operation
With `LLM_MODE=replay` or `LLM_PROVIDER=fake`, Decidr resolves prompt completions against local SHA-256 disk cache files in `backend/.llm_cache/` or deterministic fixtures. In replay mode, the platform runs completely air-gapped without making any outbound network connections.

---

## 4. Data Retention, Storage & Purging

### 4.1 Data Storage Architecture
- **Database:** Local SQLite (`decidr.db`) or enterprise PostgreSQL.
- **Audit Log:** An append-only table (`audit_log`) that enforces database-level immutability triggers: `UPDATE` and `DELETE` queries are categorically blocked by the engine (Invariant 3).
- **Reminders & Outbox:** Stored locally in table `outbox` until dispatched by the scheduled task worker.

### 4.2 Right-to-be-Forgotten: Meeting Purge API
To comply with GDPR, CCPA, and enterprise confidentiality mandates, Decidr provides a dedicated meeting deletion and purge endpoint:

#### Endpoint: `DELETE /meetings/{id}`

When invoked by an authorized reviewer or privacy officer:
1. **Transcript Text Removal:** All dialogue turn records (`Utterance` rows) containing verbatim quotes, speech text, and timestamps are permanently deleted.
2. **Derived Items Purged:** All uncommitted or derived decisions, premises, action items, task definitions, and alert cards originating from the meeting are cascade-deleted.
3. **Non-Content Audit Log Preservation (Invariant 3):** To satisfy security audit requirements without retaining sensitive dialogue content, Decidr records a single redacted audit entry:
```json
{
  "actor": "privacy_officer",
  "action": "delete_meeting",
  "entity_type": "meeting",
  "entity_id": 14,
  "before": null,
  "after": {
    "deleted": true,
    "title_redacted": true,
    "transcript_purged": true,
    "derived_items_purged": true,
    "retained_content": "none"
  }
}
```

---

## 5. Summary Compliance Matrix

| Regulation / Standard | Decidr Design Control |
| :--- | :--- |
| **GDPR Art. 17 (Right to Erasure)** | `DELETE /meetings/{id}` purges raw dialogue and derived items immediately. |
| **GDPR Art. 25 (Data Protection by Design)** | Local storage default, zero-retention LLM calls, deterministic prompt scopes. |
| **SOC 2 Type II (Change Management & Security)** | Immutable append-only audit trail (`audit_log`) tracking all human approvals. |
| **Least Privilege Execution** | Zero autonomous writes to tracker systems or email gateways (Invariant 2). |
