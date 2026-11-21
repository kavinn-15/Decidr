import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from eval.run_eval import run_evaluation, backend_path

router = APIRouter(prefix="/eval", tags=["evaluation"])


def _find_report_json() -> Optional[dict]:
    # Look in root eval/ or backend/eval/outputs/
    candidates = [
        backend_path.parent / "eval" / "report.json",
        backend_path / "eval" / "outputs" / "report.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


@router.get("/report")
def get_eval_report(
    heldout: bool = Query(False, description="Run/fetch heldout evaluation"),
):
    """
    Returns the latest evaluation report. If not found, runs evaluation and returns result.
    """
    if heldout:
        # Heldout must be explicitly requested and run
        report = run_evaluation(allow_heldout=True)
        return report

    report = _find_report_json()
    if not report:
        report = run_evaluation(allow_heldout=False)
    return report


@router.get("/report/markdown", response_class=PlainTextResponse)
def get_eval_markdown():
    """
    Returns the evaluation report in Markdown format.
    """
    candidates = [
        backend_path.parent / "eval" / "report.md",
        backend_path / "eval" / "outputs" / "report.md",
    ]
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()

    # Generate if not exists
    run_evaluation(allow_heldout=False)
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()

    raise HTTPException(status_code=404, detail="Markdown report not available")


@router.get("/report/csv", response_class=PlainTextResponse)
def get_eval_csv():
    """
    Returns the evaluation comparison table in CSV format.
    """
    candidates = [
        backend_path.parent / "eval" / "report.csv",
        backend_path / "eval" / "outputs" / "report.csv",
    ]
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()

    run_evaluation(allow_heldout=False)
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()

    raise HTTPException(status_code=404, detail="CSV report not available")


@router.post("/run")
def trigger_eval_run(
    heldout: bool = Query(False, description="Whether to evaluate on held-out dataset"),
):
    """
    Triggers execution of the evaluation pipeline and returns fresh report.
    """
    report = run_evaluation(allow_heldout=heldout)
    return report
