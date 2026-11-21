from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Alert
from app.models.enums import AlertState
from app.services.blast_radius import calculate_blast_radius

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    state: Optional[str] = Query("open", description="Filter by state (open, confirmed, dismissed, all)"),
    project: Optional[str] = Query(None, description="Filter by project"),
    db: Session = Depends(get_db),
):
    """
    List alerts for blast-radius selection and triage.
    """
    query = db.query(Alert)
    if state and state.lower() != "all":
        try:
            alert_st = AlertState(state)
            query = query.filter(Alert.state == alert_st)
        except ValueError:
            pass

    alerts = query.order_by(Alert.id.desc()).all()
    results = []
    for a in alerts:
        results.append({
            "id": a.id,
            "kind": a.kind.value,
            "verdict": a.verdict,
            "state": a.state.value,
            "meeting_id": a.meeting_id,
            "decision_id": a.decision_id,
            "premise_id": a.premise_id,
            "proposal_id": a.proposal_id,
            "old_quote": a.old_quote,
            "new_quote": a.new_quote,
            "explanation": a.explanation,
        })
    return results


@router.get("/{alert_id}/repair-plan")
def get_alert_repair_plan(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns the repair plan proposal associated with this alert.
    """
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert #{alert_id} not found")
    if not alert.proposal_id:
        raise HTTPException(status_code=404, detail=f"No repair proposal found for Alert #{alert_id}")
    from app.api.routes.proposals import get_proposal
    return get_proposal(alert.proposal_id, db=db)


@router.post("/{alert_id}/repair-plan")
def create_alert_repair_plan(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """
    Generates a deterministic rule-based repair plan for this alert.
    """
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert #{alert_id} not found")
    from app.services.repair import generate_repair_plan
    from app.api.routes.proposals import get_proposal
    try:
        proposal = generate_repair_plan(db, alert_id=alert.id)
        db.commit()
        return get_proposal(proposal.id, db=db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{alert_id}/blast-radius")
def get_alert_blast_radius(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """
    Computes deterministic blast radius and impact tracing for a given alert.
    Traversal and explanations are plain code with ZERO LLM.
    """
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert #{alert_id} not found")

    try:
        data = calculate_blast_radius(db, alert=alert)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
