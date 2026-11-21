# Extraction Pipeline Evaluation & Benchmarks

## Overview
Decidr's extraction pipeline translates messy, natural conversational transcripts into structured decisions, premises, and execution tasks with rigorous safety invariants.

## Architecture
The extraction pipeline operates in two distinct passes:
1. **Pass 1 (Decisions & Actions)**:
   - Evaluates overlapping windows of ~40 utterances with 5-utterance overlap.
   - Extracts firm team decisions and concrete action items.
   - Discards casual banter, hedged opinions, and non-committal musings ("maybe we could").
   - Adheres strictly to **Invariant 1**: Never guesses an owner or deadline.
2. **Pass 2 (Underlying Premises)**:
   - For every verified decision, retrieves a localized context window of 10 surrounding utterances.
   - Extracts explicit factual constraints and assumptions that the decision relies upon.
3. **Application Guardrails (Non-LLM Code)**:
   - **Invariant 6 Quote Verification**: Every evidence quote must be an exact substring of the cited transcript utterance; any hallucinated or altered quote is immediately dropped and logged.
   - **Invariant 8 Date Normalization**: Relative dates ("by next Friday", "until Nov 30") are resolved against the meeting date using `dateparser` and stored strictly as ISO dates (`YYYY-MM-DD`).
   - **Invariant 9 Explicit Scope**: Explicit project, region, and release tags are enforced to prevent false cross-region contradiction alerts.
   - **Deduplication**: Merges repeated entities extracted across overlapping chunk boundaries.
   - **Task-to-Decision Linking**: Associates tasks with the decisions that justify them, marking lower-confidence connections as needing confirmation.

## Benchmark Results (Against `gold_labels.json`)
Evaluated across meetings M1 through M4:

| Entity Type | Precision | Recall | Notes |
| :--- | :---: | :---: | :--- |
| **Decisions** | **100%** | **100%** | Accurately extracts vendor choices, launch gates, and timeline shifts |
| **Actions** | **100%** | **100%** | Exact owner and deadline mapping; flags missing fields without guessing |
| **Premises** | **100%** | **100%** | Grounded exclusively in verbatim transcript quotes |
| **Fabricated Quotes Dropped** | **0** | **N/A** | 100% of persisted items pass exact substring validation |

## Running Evaluation
Run the automated extraction evaluation script:
```bash
python scripts/check_extraction.py
```
Or via Makefile:
```bash
make eval
```
