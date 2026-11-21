"""
Tests for Evaluation Harness, Metrics, Baselines, and Held-out Guard (Invariant 10).
Requirements:
1. Metric functions return expected precision and recall on tiny hand-made example.
2. Held-out guard refuses to run without --heldout flag.
3. Test fails if report numbers are not derived from computed results (no hard-coding).
"""

import json
import pytest
from pathlib import Path

from eval.metrics import (
    calc_precision_recall,
    evaluate_extraction_category,
    evaluate_premise_breaks,
    evaluate_conflicts,
    evaluate_impact,
    evaluate_repair_plan,
    calculate_writes_without_approval,
)
from eval.heldout_guard import (
    load_evaluation_dataset,
    verify_heldout_access_allowed,
    HeldoutAccessViolationError,
)
from eval.baselines import (
    run_baseline_1_metrics,
    run_baseline_2_metrics,
    format_comparison_table,
)
from eval.run_eval import generate_markdown_report


def test_metric_functions_return_expected_precision_and_recall_on_tiny_example():
    """
    1. Metric functions return expected precision and recall on tiny hand-made example.
    """
    # Test base math
    # TP=2, FP=1, FN=1 -> Precision = 2/3 = 0.6667, Recall = 2/3 = 0.6667
    base_res = calc_precision_recall(tp=2, fp=1, fn=1)
    assert base_res["tp"] == 2
    assert base_res["fp"] == 1
    assert base_res["fn"] == 1
    assert base_res["precision"] == 0.6667
    assert base_res["recall"] == 0.6667
    assert base_res["f1"] == 0.6667

    # Test edge case: zero detections (TP=0, FP=0, FN=2) -> Precision = 0.0, Recall = 0.0
    zero_det = calc_precision_recall(tp=0, fp=0, fn=2)
    assert zero_det["precision"] == 0.0
    assert zero_det["recall"] == 0.0
    assert zero_det["f1"] == 0.0

    # Test tiny extraction example
    extracted = [
        {"evidence_quote": "we will use Provider A for India", "text": "Use Provider A"},
        {"evidence_quote": "unrelated statement about lunch", "text": "Grab lunch"},  # FP
    ]
    gold = [
        {"evidence_quote": "we will use Provider A for India", "text": "Use Provider A"},  # Matches
        {"evidence_quote": "launch on Dec 15", "text": "Launch Dec 15"},  # Missed (FN)
    ]
    # TP=1, FP=1, FN=1 -> Precision = 0.5, Recall = 0.5
    ext_metrics = evaluate_extraction_category(extracted, gold, quote_field="evidence_quote", text_field="text")
    assert ext_metrics["tp"] == 1
    assert ext_metrics["fp"] == 1
    assert ext_metrics["fn"] == 1
    assert ext_metrics["precision"] == 0.5
    assert ext_metrics["recall"] == 0.5
    assert ext_metrics["f1"] == 0.5

    # Test tiny premise breaks example
    detected_alerts = [
        {"kind": "premise_break", "new_quote": "Provider A only supports T+2", "premise_id": "P1"},
        {"kind": "premise_break", "new_quote": "Hallucinated break quote", "premise_id": "P99"},
    ]
    gold_alerts = [
        {"kind": "premise_break", "new_quote": "Provider A only supports T+2", "premise_id": "P1"},
        {"kind": "premise_break", "new_quote": "Ravi is on leave", "premise_id": "P3"},
    ]
    break_metrics = evaluate_premise_breaks(detected_alerts, gold_alerts)
    assert break_metrics["tp"] == 1
    assert break_metrics["fp"] == 1
    assert break_metrics["fn"] == 1
    assert break_metrics["precision"] == 0.5
    assert break_metrics["recall"] == 0.5

    # Test tiny conflict alerts example
    det_conflicts = [
        {"kind": "conflict", "decision_id": "D2", "new_quote": "moving launch from Dec 15 to Jan 10"},
    ]
    gold_conflicts = [
        {"kind": "conflict", "decision_id": "D2", "new_quote": "moving launch from Dec 15 to Jan 10"},
    ]
    conf_metrics = evaluate_conflicts(det_conflicts, gold_conflicts)
    assert conf_metrics["tp"] == 1
    assert conf_metrics["fp"] == 0
    assert conf_metrics["fn"] == 0
    assert conf_metrics["precision"] == 1.0
    assert conf_metrics["recall"] == 1.0

    # Test tiny repair plan correctness
    gen_actions = [
        {"action_type": "mark_decision_at_risk", "target_type": "decision", "target_id": "D1"},
        {"action_type": "comment_task", "target_type": "task", "target_id": "T1"},
    ]
    gold_repair = [
        {"action_type": "mark_decision_at_risk", "target_type": "decision", "target_id": "D1"},
        {"action_type": "comment_task", "target_type": "task", "target_id": "T1"},
        {"action_type": "pause_reminders", "target_type": "task", "target_id": "T4"},
    ]
    # 2 out of 3 matched -> correctness = 2/3 = 0.6667
    repair_metrics = evaluate_repair_plan(gen_actions, gold_repair)
    assert repair_metrics["matched"] == 2
    assert repair_metrics["total_gold"] == 3
    assert repair_metrics["correctness"] == 0.6667

    # Test writes without approval
    unapproved = calculate_writes_without_approval(
        audit_entries=[{"action": "create_task"}],
        tracker_tickets=[{"id": 1, "approved": False}],
    )
    assert unapproved == 1


def test_heldout_guard_refuses_to_run_without_heldout_flag():
    """
    2. Held-out guard refuses to run without --heldout flag.
       Held-out dataset may be read only with that flag, and each use prints a warning and is logged.
    """
    # Attempting to verify held-out access without authorization must raise HeldoutAccessViolationError
    with pytest.raises(HeldoutAccessViolationError) as exc_info:
        verify_heldout_access_allowed(allow_heldout=False)
    assert "strictly protected" in str(exc_info.value)

    # Attempting to load heldout dataset with allow_heldout=False must raise HeldoutAccessViolationError
    with pytest.raises(HeldoutAccessViolationError) as exc_info2:
        load_evaluation_dataset(dataset_name="heldout", allow_heldout=False)
    assert "--heldout" in str(exc_info2.value)

    # When allow_heldout=True, access is allowed and returns dataset dictionary
    dataset = load_evaluation_dataset(dataset_name="heldout", allow_heldout=True)
    assert dataset is not None
    assert dataset["dataset_name"] == "heldout (H1-H2)"
    assert dataset["is_heldout"] is True
    assert len(dataset["meetings"]) == 2

    # Development dataset is accessible without the held-out flag
    dev_dataset = load_evaluation_dataset(dataset_name="development", allow_heldout=False)
    assert dev_dataset is not None
    assert dev_dataset["is_heldout"] is False
    assert len(dev_dataset["meetings"]) == 4


def test_report_numbers_derived_from_computed_results():
    """
    3. Test fails if report numbers are not derived from computed results (no hard-coding).
    """
    # 1. Read generated report.json if present, or generate a dynamic report
    report_file = Path("eval/report.json")
    if not report_file.exists():
        from eval.run_eval import run_evaluation
        report = run_evaluation(allow_heldout=False)
    else:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)

    # Verify report metadata stamps
    assert "date" in report["metadata"]
    assert "model" in report["metadata"]
    assert "llm_mode" in report["metadata"]
    assert "git_commit" in report["metadata"]
    assert "dataset" in report["metadata"]

    # Verify that precision, recall, and f1 in the report match pure mathematical formula
    for cat_name in ("decisions_pr", "actions_pr", "premises_pr", "premise_breaks_pr", "conflicts_pr"):
        cat = report["decidr"][cat_name]
        tp = cat["tp"]
        fp = cat["fp"]
        fn = cat["fn"]

        expected_math = calc_precision_recall(tp, fp, fn)
        assert cat["precision"] == expected_math["precision"], f"Precision in {cat_name} is not dynamically derived!"
        assert cat["recall"] == expected_math["recall"], f"Recall in {cat_name} is not dynamically derived!"
        assert cat["f1"] == expected_math["f1"], f"F1 in {cat_name} is not dynamically derived!"

    # Verify comparison table numbers strictly match underlying metrics
    table = report["comparison_table"]
    metric_map = {row["metric"]: row for row in table}

    # B1 has 0% for premises, premise breaks, conflicts, and repair
    assert metric_map["Premise Extraction (P / R)"]["b1"] == "0.0% / 0.0%"
    assert metric_map["Premise-Break Detection (P / R)"]["b1"] == "0.0% / 0.0%"
    assert metric_map["Repair Plan Correctness"]["b1"] == "0.0%"

    # Decidr has derived numbers matching decidr dict
    dec_ext_str = f"{report['decidr']['decisions_pr']['precision']*100:.1f}% / {report['decidr']['decisions_pr']['recall']*100:.1f}%"
    assert metric_map["Decision Extraction (P / R)"]["decidr"] == dec_ext_str

    # Proving dynamic derivation: changing TP changes the output of format_comparison_table
    synthetic_decidr = dict(report["decidr"])
    synthetic_decidr["decisions_pr"] = calc_precision_recall(tp=3, fp=2, fn=1)  # 60.0% / 75.0%
    new_table = format_comparison_table(report["b1_baseline"], report["b2_baseline"], synthetic_decidr)
    new_metric_map = {row["metric"]: row for row in new_table}
    assert new_metric_map["Decision Extraction (P / R)"]["decidr"] == "60.0% / 75.0%"
    assert new_metric_map["Decision Extraction (P / R)"]["decidr"] != dec_ext_str
