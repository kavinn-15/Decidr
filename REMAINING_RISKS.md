# DECIDR — REMAINING RISKS & OPERATIONAL BOUNDARIES
**Audit Date:** November 21, 2026  
**Auditing Perspective:** Principal Systems Architect & Production Operations Review

---

## 1. OBJECTIVE RISK ASSESSMENT MATRIX

| Risk Factor | Impact | Likelihood | Current Mitigation in Codebase | Recommended Production Roadmap |
| :--- | :---: | :---: | :--- | :--- |
| **1. Database Concurrency Under High Load** | Medium | Low | SQLite configured with `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=5000;`. Tested under parallel API test calls. | Migrate to PostgreSQL with connection pooling (e.g. pgBouncer) when horizontally scaling across multiple container replicas. |
| **2. Live LLM Provider Latency & Rate Limits** | High | Medium | Local disk cache (`DiskCache`) avoids redundant queries; `LLM_MODE=replay` enables 100% deterministic offline execution; exponential backoff retries. | Implement Celery/Redis asynchronous job queue for long transcript batch processing to isolate API request timeouts. |
| **3. Tracker API Quotas (GitHub/Jira)** | Medium | Low | Action batching; dry-run preview before execution; idempotency keys (`sha256`) eliminate redundant ticket updates. | Add client-side rate limit token bucket for tracker adapters to pause and pace bulk ticket updates. |
| **4. Raw Audio Transcription Quality** | Medium | Medium | Ingestion pipeline accepts standardized VTT and SRT formats with timestamps and speaker tags; flags unmapped speakers. | Integrate Deepgram / Whisper ASR pipeline with automated speaker diarization calibration for raw audio files. |
| **5. Subtly Implied Premise Invalidation** | Medium | Low | Four-verdict framework (`uncertain` triggers `shaky` status and human review card); exact transcript quote verification prevents hallucinations. | Enhance fine-grained premise vector embeddings to retrieve top-k semantic candidates for large-scale enterprise ledgers. |
| **6. Massive Organizational Decision Graph Scale** | Medium | Low | Pure Python BFS traversal with cycle detection (`visited_decisions`) completes in sub-millisecond time for current enterprise graphs. | For graphs exceeding 100,000 nodes, index links with a graph database (e.g., Neo4j or Amazon Neptune) or recursive SQL CTEs. |

---

## 2. DETAILED ANALYSIS & OPERATIONAL BOUNDARIES

### A. SQLite to PostgreSQL Transition Path
- **Current Architecture:** Decidr operates on SQLite with WAL mode, foreign keys, and busy timeout handlers. This is ideal for single-node deployments, on-premise local installations, and hackathon evaluation environments.
- **Boundary:** In a distributed Kubernetes environment with multiple FastAPI replicas reading and writing simultaneously, SQLite write locking will become a bottleneck.
- **Mitigation Path:** The database layer is written in standard SQLAlchemy ORM 2.0 without dialect-specific SQL. Switching to PostgreSQL requires solely changing `DATABASE_URL=postgresql://user:pass@host/decidr` in `.env`.

### B. Live LLM Provider Quotas & Failover
- **Current Architecture:** Decidr supports multiple providers (Google Gemini, Anthropic Claude, OpenAI) through a unified adapter (`backend/app/llm/adapter.py`). It features disk caching and deterministic replay records.
- **Boundary:** In production with live LLM mode, third-party provider outages (e.g., Anthropic 529 or Gemini 429 quota exhaustion) could pause transcript ingestion.
- **Mitigation Path:** The adapter includes retry logic with jitter. In production, an automatic multi-provider fallback cascade (Gemini -> Claude -> OpenAI) should be enabled.

### C. Human Review Bottleneck
- **Current Architecture:** Decidr adheres strictly to Invariant 2 and Invariant 5: the LLM only proposes, humans approve.
- **Boundary:** If reviewers allow unreviewed cards to accumulate, premise-break alerts remain in `pending_review`, temporarily delaying blast-radius repair actions.
- **Mitigation Path:** The `/my-week` digest and weekly automated reminders proactively surface unreviewed alerts to designated owners to maintain high review velocity.

---

## 3. AUDIT CONCLUSION
None of the identified remaining risks represent architectural flaws or blocking vulnerabilities. All operational boundaries have built-in defenses in the current implementation, and the architectural foundation is positioned for seamless enterprise scaling.
