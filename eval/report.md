# DECIDR EVALUATION REPORT

**Date:** 2026-11-21T16:21:00.642832+00:00  
**Model:** `gemini-1.5-pro`  
**LLM Mode:** `live`  
**Git Commit:** `fac8b1c5e3f61f65265d1e4e564cf03041ac0eb2`  
**Dataset:** `development (M1-M4)`  

---

## Baseline Comparison

| Metric | B1 Baseline (Extraction Only) | B2 Baseline (Extraction + Pairwise Conflicts) | Decidr Platform (Full) |
| :--- | :--- | :--- | :--- |
| Decision Extraction (P / R) | 100.0% / 100.0% | 100.0% / 100.0% | 100.0% / 100.0% |
| Action Extraction (P / R) | 100.0% / 100.0% | 100.0% / 100.0% | 100.0% / 100.0% |
| Premise Extraction (P / R) | 0.0% / 0.0% | 0.0% / 0.0% | 100.0% / 100.0% |
| Premise-Break Detection (P / R) | 0.0% / 0.0% | 0.0% / 0.0% | 100.0% / 100.0% |
| Cross-Decision Conflict (P / R) | 0.0% / 0.0% | 100.0% / 100.0% | 100.0% / 100.0% |
| Impact / Affected Tasks (P / R) | 0.0% / 0.0% | 0.0% / 0.0% | 80.0% / 80.0% |
| Repair Plan Correctness | 0.0% | 0.0% | 71.4% |
| Writes Without Approval (Target 0) | 0 | 0 | 0 |

---

## Detailed Metrics Breakdown

### 1. Two-Pass Extraction
- **Decisions**: Precision = `100.0%`, Recall = `100.0%` (TP=6, FP=0, FN=0)
- **Actions**: Precision = `100.0%`, Recall = `100.0%` (TP=7, FP=0, FN=0)
- **Premises**: Precision = `100.0%`, Recall = `100.0%` (TP=4, FP=0, FN=0)

### 2. Detection Systems
- **Premise-Break Detection**: Precision = `100.0%`, Recall = `100.0%` (TP=2, FP=0, FN=0)
- **Cross-Decision Conflict**: Precision = `100.0%`, Recall = `100.0%` (TP=1, FP=0, FN=0)

### 3. Impact & Execution Safety
- **Impact (Affected Tasks) Accuracy**: Precision = `80.0%`, Recall = `80.0%`
- **Repair Plan Correctness**: `71.4%` (5/7 matching actions)
- **Writes Without Approval**: `0` (Strict Target 0: Invariant 2 Enforced)

---
*Report generated deterministically from live pipeline output versus gold labels (Invariant 10).*  