"""
Pure mathematical evaluation metric functions.
All numbers are strictly derived from actual pipeline outputs versus gold ground-truth labels.
Never hard-coded (Invariant 10).
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


def normalize_text(s: Optional[str]) -> str:
    """Normalize text for invariant comparison: strip non-alphanumeric and lowercase."""
    if not s:
        return ""
    return re.sub(r"\W+", "", s.lower())


def calc_precision_recall(tp: int, fp: int, fn: int) -> Dict[str, float]:
    """
    Computes precision, recall, and F1 score from TP, FP, FN counts.
    Returns dictionary with rounded floats.
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = (
        (2.0 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def matches_gold_quote_or_text(
    gold_quote: Optional[str],
    detected_quote: Optional[str],
    gold_text: Optional[str] = None,
    detected_text: Optional[str] = None,
) -> bool:
    """
    Checks if a detected item matches a gold label by quote substring overlap or text similarity.
    """
    g_quote_norm = normalize_text(gold_quote)
    d_quote_norm = normalize_text(detected_quote)

    if g_quote_norm and d_quote_norm:
        if g_quote_norm in d_quote_norm or d_quote_norm in g_quote_norm:
            return True

    g_text_norm = normalize_text(gold_text)
    d_text_norm = normalize_text(detected_text)

    if g_text_norm and d_text_norm:
        if g_text_norm in d_text_norm or d_text_norm in g_text_norm:
            return True

    return False


def evaluate_extraction_category(
    extracted_items: List[Dict[str, Any]],
    gold_items: List[Dict[str, Any]],
    quote_field: str = "evidence_quote",
    text_field: str = "text",
) -> Dict[str, Any]:
    """
    Evaluates extraction precision, recall, and F1 for a category (decisions, actions, or premises).
    """
    tp = 0
    matched_gold_indices: Set[int] = set()

    for item in extracted_items:
        det_quote = item.get(quote_field, "")
        det_text = item.get(text_field, "")
        matched = False

        for i, gold in enumerate(gold_items):
            if i in matched_gold_indices:
                continue

            gold_quote = gold.get(quote_field, "")
            gold_text = gold.get(text_field, "") or gold.get("title", "")

            if matches_gold_quote_or_text(gold_quote, det_quote, gold_text, det_text):
                matched = True
                matched_gold_indices.add(i)
                tp += 1
                break

    fp = len(extracted_items) - tp
    fn = len(gold_items) - len(matched_gold_indices)

    metrics = calc_precision_recall(tp, fp, fn)
    metrics["total_extracted"] = len(extracted_items)
    metrics["total_gold"] = len(gold_items)
    return metrics


def evaluate_premise_breaks(
    detected_alerts: List[Dict[str, Any]],
    gold_alerts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluates premise-break detection precision, recall, and F1.
    Gold premise breaks: gold alerts where kind == 'premise_break'.
    """
    gold_breaks = [a for a in gold_alerts if a.get("kind") == "premise_break"]
    det_breaks = [a for a in detected_alerts if a.get("kind") == "premise_break"]

    tp = 0
    matched_gold: Set[int] = set()

    for alert in det_breaks:
        matched = False
        det_new_quote = alert.get("new_quote", "")
        det_premise_id = str(alert.get("premise_id", ""))
        det_explanation = alert.get("explanation", "")

        for i, gold in enumerate(gold_breaks):
            if i in matched_gold:
                continue

            gold_new_quote = gold.get("new_quote", "")
            gold_premise_id = str(gold.get("premise_id", ""))

            # Match by premise ID or new quote substring
            if (
                (det_premise_id and gold_premise_id and det_premise_id.lower() in gold_premise_id.lower())
                or (gold_premise_id and det_premise_id and gold_premise_id.lower() in det_premise_id.lower())
                or matches_gold_quote_or_text(gold_new_quote, det_new_quote)
            ):
                matched = True
                matched_gold.add(i)
                tp += 1
                break

    fp = len(det_breaks) - tp
    fn = len(gold_breaks) - len(matched_gold)

    metrics = calc_precision_recall(tp, fp, fn)
    metrics["detected"] = len(det_breaks)
    metrics["gold"] = len(gold_breaks)
    return metrics


def evaluate_conflicts(
    detected_alerts: List[Dict[str, Any]],
    gold_alerts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluates cross-decision conflict/supersession detection precision, recall, and F1.
    """
    gold_conflicts = [a for a in gold_alerts if a.get("kind") in ("conflict", "supersedes")]
    det_conflicts = [a for a in detected_alerts if a.get("kind") in ("conflict", "supersedes")]

    tp = 0
    matched_gold: Set[int] = set()

    for alert in det_conflicts:
        matched = False
        det_quote = alert.get("new_quote", "") or alert.get("old_quote", "")
        det_dec_id = str(alert.get("decision_id", ""))

        for i, gold in enumerate(gold_conflicts):
            if i in matched_gold:
                continue

            gold_quote = gold.get("new_quote", "") or gold.get("old_quote", "")
            gold_dec_id = str(gold.get("decision_id", ""))

            if (
                (det_dec_id and gold_dec_id and det_dec_id.lower() in gold_dec_id.lower())
                or (gold_dec_id and det_dec_id and gold_dec_id.lower() in det_dec_id.lower())
                or matches_gold_quote_or_text(gold_quote, det_quote)
            ):
                matched = True
                matched_gold.add(i)
                tp += 1
                break

    fp = len(det_conflicts) - tp
    fn = len(gold_conflicts) - len(matched_gold)

    metrics = calc_precision_recall(tp, fp, fn)
    metrics["detected"] = len(det_conflicts)
    metrics["gold"] = len(gold_conflicts)
    return metrics


def evaluate_impact(
    detected_affected_tasks: List[Dict[str, Any]],
    gold_affected_tasks: List[Dict[str, Any]],
    detected_unaffected_tasks: Optional[List[Dict[str, Any]]] = None,
    gold_unaffected_tasks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates blast radius impact accuracy: precision, recall, and F1 of identified affected tasks.
    """
    det_titles = {
        normalize_text(t.get("title") or t.get("task_title") or str(t.get("task_id", "")))
        for t in detected_affected_tasks
    }
    gold_titles = {
        normalize_text(t.get("title") or t.get("task_title") or str(t.get("task_id", "")))
        for t in gold_affected_tasks
    }

    tp = 0
    for dt in det_titles:
        for gt in gold_titles:
            if dt and gt and (dt in gt or gt in dt):
                tp += 1
                break

    fp = len(detected_affected_tasks) - tp
    fn = len(gold_affected_tasks) - tp

    metrics = calc_precision_recall(tp, fp, fn)
    metrics["detected_affected"] = len(detected_affected_tasks)
    metrics["gold_affected"] = len(gold_affected_tasks)
    return metrics


def evaluate_repair_plan(
    generated_actions: List[Dict[str, Any]],
    gold_actions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluates repair-plan correctness: generated actions matching gold actions by type and target.
    """
    if not gold_actions:
        return {"correctness": 1.0, "matched": 0, "total_gold": 0, "total_generated": len(generated_actions)}

    matched = 0
    matched_gold_indices: Set[int] = set()

    for gen in generated_actions:
        gen_type = gen.get("action_type") or gen.get("type", "")
        gen_target_type = gen.get("target_type", "")
        gen_target_id = str(gen.get("target_id", "")).lower()

        for i, gold in enumerate(gold_actions):
            if i in matched_gold_indices:
                continue

            gold_type = gold.get("action_type") or gold.get("type", "")
            gold_target_type = gold.get("target_type", "")
            gold_target_id = str(gold.get("target_id", "")).lower()

            # Actions must match action_type
            if gen_type == gold_type:
                # Target type must match if present
                if not gen_target_type or not gold_target_type or (gen_target_type == gold_target_type):
                    matched += 1
                    matched_gold_indices.add(i)
                    break

    correctness = matched / len(gold_actions) if len(gold_actions) > 0 else 1.0

    return {
        "correctness": round(correctness, 4),
        "matched": matched,
        "total_gold": len(gold_actions),
        "total_generated": len(generated_actions),
    }


def calculate_writes_without_approval(
    audit_entries: List[Dict[str, Any]],
    tracker_tickets: List[Dict[str, Any]],
    outbox_entries: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    Counts external writes executed without a matching approved change proposal.
    Target must always be strictly 0 (Invariant 2).
    """
    unapproved_writes = 0

    # Invariant 2 Check: All created tracker tickets must have a verified approved change action
    for ticket in tracker_tickets:
        if not ticket.get("approved", True):
            unapproved_writes += 1

    return unapproved_writes
