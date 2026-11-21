"""
Baselines runner for comparison against Decidr:
- Baseline 1 (B1): Extraction plus task creation only.
- Baseline 2 (B2): Extraction plus pairwise decision-versus-decision contradiction detection only (no premises).
- Decidr: Full platform (extraction + premises + cross-decision conflicts + continuous premise watch + BFS blast radius + repair).
"""

from typing import Any, Dict, List
from eval.metrics import (
    evaluate_extraction_category,
    evaluate_premise_breaks,
    evaluate_conflicts,
    evaluate_impact,
    evaluate_repair_plan,
    calculate_writes_without_approval,
)


def run_baseline_1_metrics(
    extraction_results: Dict[str, Any],
    gold_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    B1: Extraction plus task creation only.
    - Captures extracted items.
    - Zero premise monitoring.
    - Zero conflict detection.
    - Zero impact tracking or repair plans.
    """
    return {
        "name": "B1: Extraction + Task Creation Only",
        "description": "Naive extraction directly into task issues. No premise tracking, no conflict detection, no repair.",
        "decisions_pr": extraction_results.get("decisions", {}),
        "actions_pr": extraction_results.get("actions", {}),
        "premises_pr": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": extraction_results.get("premises", {}).get("total_gold", 0)},
        "premise_breaks_pr": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 2},
        "conflicts_pr": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 1},
        "impact_pr": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 4},
        "repair_correctness": {"correctness": 0.0, "matched": 0, "total_gold": 4, "total_generated": 0},
        "writes_without_approval": 0,
    }


def run_baseline_2_metrics(
    extraction_results: Dict[str, Any],
    conflict_results: Dict[str, Any],
    gold_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    B2: Extraction plus pairwise decision-versus-decision contradiction detection only (no premises).
    - Captures extracted decisions and tasks.
    - Captures direct decision-vs-decision conflicts (e.g. M3 launch date change).
    - Blind to passing dialogue remarks undermining implicit premises (e.g. Sam in M2).
    - Zero premise-based blast radius or task repairs.
    """
    return {
        "name": "B2: Extraction + Pairwise Decision Contradictions Only",
        "description": "Extracts decisions and detects direct decision-vs-decision contradictions. No premise monitoring or blast radius.",
        "decisions_pr": extraction_results.get("decisions", {}),
        "actions_pr": extraction_results.get("actions", {}),
        "premises_pr": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": extraction_results.get("premises", {}).get("total_gold", 0)},
        "premise_breaks_pr": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 2},
        "conflicts_pr": conflict_results,
        "impact_pr": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 4},
        "repair_correctness": {"correctness": 0.0, "matched": 0, "total_gold": 4, "total_generated": 0},
        "writes_without_approval": 0,
    }


def format_comparison_table(
    b1_metrics: Dict[str, Any],
    b2_metrics: Dict[str, Any],
    decidr_metrics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Formats comparison rows across B1, B2, and Decidr for table output.
    """
    def _pct(val: Any) -> str:
        if isinstance(val, (int, float)):
            return f"{val * 100:.1f}%"
        return str(val)

    rows = [
        {
            "metric": "Decision Extraction (P / R)",
            "b1": f"{_pct(b1_metrics['decisions_pr'].get('precision', 0))} / {_pct(b1_metrics['decisions_pr'].get('recall', 0))}",
            "b2": f"{_pct(b2_metrics['decisions_pr'].get('precision', 0))} / {_pct(b2_metrics['decisions_pr'].get('recall', 0))}",
            "decidr": f"{_pct(decidr_metrics['decisions_pr'].get('precision', 0))} / {_pct(decidr_metrics['decisions_pr'].get('recall', 0))}",
        },
        {
            "metric": "Action Extraction (P / R)",
            "b1": f"{_pct(b1_metrics['actions_pr'].get('precision', 0))} / {_pct(b1_metrics['actions_pr'].get('recall', 0))}",
            "b2": f"{_pct(b2_metrics['actions_pr'].get('precision', 0))} / {_pct(b2_metrics['actions_pr'].get('recall', 0))}",
            "decidr": f"{_pct(decidr_metrics['actions_pr'].get('precision', 0))} / {_pct(decidr_metrics['actions_pr'].get('recall', 0))}",
        },
        {
            "metric": "Premise Extraction (P / R)",
            "b1": f"{_pct(b1_metrics['premises_pr'].get('precision', 0))} / {_pct(b1_metrics['premises_pr'].get('recall', 0))}",
            "b2": f"{_pct(b2_metrics['premises_pr'].get('precision', 0))} / {_pct(b2_metrics['premises_pr'].get('recall', 0))}",
            "decidr": f"{_pct(decidr_metrics['premises_pr'].get('precision', 0))} / {_pct(decidr_metrics['premises_pr'].get('recall', 0))}",
        },
        {
            "metric": "Premise-Break Detection (P / R)",
            "b1": f"{_pct(b1_metrics['premise_breaks_pr'].get('precision', 0))} / {_pct(b1_metrics['premise_breaks_pr'].get('recall', 0))}",
            "b2": f"{_pct(b2_metrics['premise_breaks_pr'].get('precision', 0))} / {_pct(b2_metrics['premise_breaks_pr'].get('recall', 0))}",
            "decidr": f"{_pct(decidr_metrics['premise_breaks_pr'].get('precision', 0))} / {_pct(decidr_metrics['premise_breaks_pr'].get('recall', 0))}",
        },
        {
            "metric": "Cross-Decision Conflict (P / R)",
            "b1": f"{_pct(b1_metrics['conflicts_pr'].get('precision', 0))} / {_pct(b1_metrics['conflicts_pr'].get('recall', 0))}",
            "b2": f"{_pct(b2_metrics['conflicts_pr'].get('precision', 0))} / {_pct(b2_metrics['conflicts_pr'].get('recall', 0))}",
            "decidr": f"{_pct(decidr_metrics['conflicts_pr'].get('precision', 0))} / {_pct(decidr_metrics['conflicts_pr'].get('recall', 0))}",
        },
        {
            "metric": "Impact / Affected Tasks (P / R)",
            "b1": f"{_pct(b1_metrics['impact_pr'].get('precision', 0))} / {_pct(b1_metrics['impact_pr'].get('recall', 0))}",
            "b2": f"{_pct(b2_metrics['impact_pr'].get('precision', 0))} / {_pct(b2_metrics['impact_pr'].get('recall', 0))}",
            "decidr": f"{_pct(decidr_metrics['impact_pr'].get('precision', 0))} / {_pct(decidr_metrics['impact_pr'].get('recall', 0))}",
        },
        {
            "metric": "Repair Plan Correctness",
            "b1": _pct(b1_metrics['repair_correctness'].get('correctness', 0)),
            "b2": _pct(b2_metrics['repair_correctness'].get('correctness', 0)),
            "decidr": _pct(decidr_metrics['repair_correctness'].get('correctness', 0)),
        },
        {
            "metric": "Writes Without Approval (Target 0)",
            "b1": str(b1_metrics['writes_without_approval']),
            "b2": str(b2_metrics['writes_without_approval']),
            "decidr": str(decidr_metrics['writes_without_approval']),
        },
    ]

    return rows
