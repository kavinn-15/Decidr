"""
Held-out dataset access guard enforcing Invariant 10.
The held-out set may be read ONLY with the --heldout flag.
Each use prints a prominent warning and is logged.
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("decidr.eval.heldout_guard")


class HeldoutAccessViolationError(PermissionError):
    """Raised when an attempt is made to access held-out data without the explicit --heldout flag."""
    pass


def verify_heldout_access_allowed(allow_heldout: bool) -> None:
    """
    Guards access to the held-out evaluation dataset.
    Raises HeldoutAccessViolationError if allow_heldout is False.
    """
    if not allow_heldout:
        error_msg = (
            "Access to the held-out evaluation dataset is strictly protected (Invariant 10). "
            "You must pass the explicit '--heldout' flag to access held-out data."
        )
        logger.error(error_msg)
        raise HeldoutAccessViolationError(error_msg)

    # Print prominent warning and log
    timestamp = datetime.now(timezone.utc).isoformat()
    warning_banner = (
        "\n"
        "********************************************************************************\n"
        "[WARNING] ACCESSING HELD-OUT EVALUATION DATASET (Invariant 10 Enforcement)\n"
        f"Timestamp: {timestamp}\n"
        "Notice: Held-out dataset usage is strictly monitored and audited.\n"
        "********************************************************************************\n"
    )
    print(warning_banner, file=sys.stderr)
    logger.warning(
        f"Held-out dataset accessed with authorization at {timestamp}."
    )


def load_evaluation_dataset(
    dataset_name: str = "development",
    allow_heldout: bool = False,
    base_dir: str = "",
) -> Dict[str, Any]:
    """
    Loads either the development (M1..M4) or held-out (H1..H2) dataset with safety guard.
    """
    import json

    base_path = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent / "seed"

    if dataset_name.lower() in ("heldout", "held_out", "held-out"):
        verify_heldout_access_allowed(allow_heldout)
        heldout_dir = base_path / "heldout"
        gold_path = heldout_dir / "gold_labels_heldout.json"
        roster_path = heldout_dir / "roster_heldout.json"

        with open(gold_path, "r", encoding="utf-8") as f:
            gold_labels = json.load(f)
        with open(roster_path, "r", encoding="utf-8") as f:
            roster = json.load(f)

        return {
            "dataset_name": "heldout (H1-H2)",
            "is_heldout": True,
            "gold_labels": gold_labels,
            "roster": roster,
            "directory": str(heldout_dir),
            "meetings": [
                {
                    "key": "H1",
                    "filename": "h1_2026-10-05.vtt",
                    "path": str(heldout_dir / "h1_2026-10-05.vtt"),
                    "title": "Mobile App Offline Cache Architecture",
                    "date": "2026-10-05",
                    "project": "Mobile App Release",
                    "region": "Global",
                },
                {
                    "key": "H2",
                    "filename": "h2_2026-10-12.vtt",
                    "path": str(heldout_dir / "h2_2026-10-12.vtt"),
                    "title": "Mobile App Latency Profiling Review",
                    "date": "2026-10-12",
                    "project": "Mobile App Release",
                    "region": "Global",
                },
            ],
        }

    # Development Set (M1..M4)
    gold_path = base_path / "gold_labels.json"
    roster_path = base_path / "roster.json"

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_labels = json.load(f)
    with open(roster_path, "r", encoding="utf-8") as f:
        roster = json.load(f)

    return {
        "dataset_name": "development (M1-M4)",
        "is_heldout": False,
        "gold_labels": gold_labels,
        "roster": roster,
        "directory": str(base_path),
        "meetings": [
            {
                "key": "M1",
                "filename": "m1_2026-11-02.vtt",
                "path": str(base_path / "m1_2026-11-02.vtt"),
                "title": "Payments Architecture Kickoff",
                "date": "2026-11-02",
                "project": "Payments Revamp",
                "region": "India",
            },
            {
                "key": "M2",
                "filename": "m2_2026-11-09.vtt",
                "path": str(base_path / "m2_2026-11-09.vtt"),
                "title": "Vendor SLA & European Launch Review",
                "date": "2026-11-09",
                "project": "Payments Revamp",
                "region": "India",
            },
            {
                "key": "M3",
                "filename": "m3_2026-11-16.vtt",
                "path": str(base_path / "m3_2026-11-16.vtt"),
                "title": "Timeline Adjustment & Launch Checklist",
                "date": "2026-11-16",
                "project": "Payments Revamp",
                "region": "India",
            },
            {
                "key": "M4",
                "filename": "m4_2026-11-23.vtt",
                "path": str(base_path / "m4_2026-11-23.vtt"),
                "title": "Sandbox Token & End-to-End Testing",
                "date": "2026-11-23",
                "project": "Payments Revamp",
                "region": "India",
            },
        ],
    }
