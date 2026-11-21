import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from app.models.models import (
    Premise,
    Decision,
    Task,
    Link,
    Alert,
    Meeting,
    Utterance,
    Item,
)
from app.models.enums import (
    LinkRelation,
    TaskStatus,
    PremiseStatus,
    AlertKind,
)
from app.services.ledger import scope_overlap

logger = logging.getLogger("decidr.blast_radius")


def calculate_blast_radius(
    db: Session,
    premise_id: Optional[int] = None,
    decision_id: Optional[int] = None,
    alert_id: Optional[int] = None,
    alert: Optional[Alert] = None,
) -> Dict[str, Any]:
    """
    Computes deterministic blast radius and impact tracing using plain code with ZERO LLM.
    Invariant 4 & 5: Traversal walks CONFIRMED links only.
    - Premise > direct decision > transitive decisions via confirmed depends_on links > tasks via confirmed implements links.
    - Categorizes tasks into:
        1. Affected (depth 1 direct, depth 2+ indirect, exact node/edge chain and templated explanation)
        2. Needs confirmation (tasks with unconfirmed candidate links, 'nothing changed')
        3. Unaffected (with code-generated reason: scope differences or no confirmed links)
    - Computes hours_at_risk = sum of estimate_hours of affected open tasks + count of unestimated tasks (Invariant 10).
    """
    if alert_id and not alert:
        alert = db.get(Alert, alert_id)

    if alert:
        if alert.premise_id:
            premise_id = alert.premise_id
        elif alert.decision_id:
            decision_id = alert.decision_id

    root_premise: Optional[Premise] = None
    root_decision: Optional[Decision] = None

    if premise_id:
        root_premise = db.get(Premise, premise_id)
        if not root_premise:
            raise ValueError(f"Premise #{premise_id} not found")
        root_decision = db.get(Decision, root_premise.decision_id)
        if not root_decision:
            raise ValueError(f"Linked decision for premise #{premise_id} not found")
        project = root_premise.scope_project
        root_region = root_premise.scope_region or root_decision.scope_region
    elif decision_id:
        root_decision = db.get(Decision, decision_id)
        if not root_decision:
            raise ValueError(f"Decision #{decision_id} not found")
        project = root_decision.scope_project
        root_region = root_decision.scope_region
    else:
        raise ValueError("Must provide either premise_id, decision_id, or alert_id")

    # 1. Trigger Evidence Formatting
    speaker = "Unknown"
    meeting_title = "Meeting"
    meeting_date_str = ""
    new_quote = ""
    old_quote = ""
    explanation = ""

    if alert:
        meeting = db.get(Meeting, alert.meeting_id) if alert.meeting_id else None
        utterance = db.get(Utterance, alert.utterance_id) if alert.utterance_id else None
        if utterance and utterance.speaker_raw:
            speaker = utterance.speaker_raw
        elif alert.explanation and "Speaker: " in alert.explanation:
            m_spk = re.search(r"Speaker:\s*([^.]+)", alert.explanation)
            if m_spk:
                speaker = m_spk.group(1).strip()
        else:
            speaker = "Participant"

        if meeting:
            meeting_title = meeting.title
            meeting_date_str = meeting.date.strftime("%b %d") if meeting.date else ""
        new_quote = alert.new_quote or ""
        old_quote = alert.old_quote or (root_premise.evidence_quote if root_premise else "")
        explanation = alert.explanation or ""

        if root_premise:
            trigger_prefix = f'{speaker} ({meeting_title}, {meeting_date_str}) says "{new_quote}" > undermines premise P{root_premise.id}'
        else:
            trigger_prefix = f'{speaker} ({meeting_title}, {meeting_date_str}) says "{new_quote}" > supersedes decision D{root_decision.id}'
    else:
        if root_premise:
            old_quote = root_premise.evidence_quote
            trigger_prefix = f'Premise P{root_premise.id} ("{root_premise.text}") is broken'
        else:
            trigger_prefix = f'Decision D{root_decision.id} ("{root_decision.text}") is superseded'

    # 2. Transitive Graph Traversal over Decisions (CONFIRMED depends_on links only)
    # Map decision_id -> (depth, list_of_node_tuples, list_of_edge_dicts, Decision)
    affected_decisions: Dict[int, Tuple[int, List[Tuple[str, int]], List[Dict[str, str]], Decision]] = {}

    initial_nodes = []
    initial_edges = []
    if root_premise:
        initial_nodes.append(("premise", root_premise.id))
        initial_nodes.append(("decision", root_decision.id))
        initial_edges.append({
            "from_type": "premise",
            "from_id": f"P{root_premise.id}",
            "to_type": "decision",
            "to_id": f"D{root_decision.id}",
            "relation": "supports",
        })
    else:
        initial_nodes.append(("decision", root_decision.id))

    # root_decision is at depth 1 for tasks directly under it
    affected_decisions[root_decision.id] = (1, initial_nodes, initial_edges, root_decision)

    queue = [root_decision.id]
    visited_decisions: Set[int] = {root_decision.id}

    while queue:
        curr_d_id = queue.pop(0)
        curr_depth, curr_nodes, curr_edges, curr_d = affected_decisions[curr_d_id]

        # Find decisions that depend on curr_d_id with confirmed depends_on links
        # Child depends on Parent (source=Child, target=Parent, relation=depends_on)
        dep_links = (
            db.query(Link)
            .filter(
                Link.target_type == "decision",
                Link.target_id == curr_d_id,
                Link.source_type == "decision",
                Link.relation == LinkRelation.depends_on,
                Link.confirmed == True,  # Invariant 4: Confirmed only
            )
            .all()
        )

        for lnk in dep_links:
            child_d_id = lnk.source_id
            if child_d_id not in visited_decisions:
                child_d = db.get(Decision, child_d_id)
                if child_d:
                    visited_decisions.add(child_d_id)
                    child_depth = curr_depth + 1
                    child_nodes = list(curr_nodes) + [("decision", child_d.id)]
                    child_edges = list(curr_edges) + [{
                        "from_type": "decision",
                        "from_id": f"D{curr_d_id}",
                        "to_type": "decision",
                        "to_id": f"D{child_d_id}",
                        "relation": "depends_on",
                    }]
                    affected_decisions[child_d_id] = (child_depth, child_nodes, child_edges, child_d)
                    queue.append(child_d_id)

    # 3. Find Tasks connected to affected decisions
    affected_decision_ids = set(affected_decisions.keys())

    # Check unconfirmed links to affected decisions (Needs Confirmation category)
    unconfirmed_task_links = (
        db.query(Link)
        .filter(
            Link.source_type == "task",
            Link.target_type == "decision",
            Link.target_id.in_(affected_decision_ids),
            Link.confirmed == False,  # Unconfirmed!
        )
        .all()
    )
    unconfirmed_task_ids = {lnk.source_id for lnk in unconfirmed_task_links}

    # Find tasks connected by confirmed implements links
    confirmed_task_links = (
        db.query(Link)
        .filter(
            Link.source_type == "task",
            Link.target_type == "decision",
            Link.target_id.in_(affected_decision_ids),
            Link.relation == LinkRelation.implements,
            Link.confirmed == True,
        )
        .all()
    )

    # Also tasks with direct task.decision_id in affected_decision_ids
    direct_tasks = (
        db.query(Task)
        .filter(Task.decision_id.in_(affected_decision_ids))
        .all()
    )

    # Map task_id -> (task, depth, chain_nodes, chain_edges, reason)
    affected_tasks_map: Dict[int, Dict[str, Any]] = {}

    for lnk in confirmed_task_links:
        task = db.get(Task, lnk.source_id)
        if not task:
            continue
        d_id = lnk.target_id
        depth, d_nodes, d_edges, d_obj = affected_decisions[d_id]

        chain_nodes = list(d_nodes) + [("task", task.id)]
        chain_edges = list(d_edges) + [{
            "from_type": "decision",
            "from_id": f"D{d_id}",
            "to_type": "task",
            "to_id": f"T{task.id}",
            "relation": "implements",
        }]

        # Generate templated reason string
        if root_premise:
            if depth == 1:
                reason = f"{trigger_prefix} > P{root_premise.id} supports D{d_obj.id} > D{d_obj.id} justifies T{task.id} ({task.title})"
            else:
                reason = f"{trigger_prefix} > P{root_premise.id} supports D{root_decision.id} > D{d_obj.id} depends on D{root_decision.id} > D{d_obj.id} justifies T{task.id} ({task.title})"
        else:
            if depth == 1:
                reason = f"{trigger_prefix} > D{d_obj.id} justifies T{task.id} ({task.title})"
            else:
                reason = f"{trigger_prefix} > D{d_obj.id} depends on D{root_decision.id} > D{d_obj.id} justifies T{task.id} ({task.title})"

        affected_tasks_map[task.id] = {
            "task": task,
            "depth": depth,
            "decision_id": d_id,
            "chain_nodes": chain_nodes,
            "chain_edges": chain_edges,
            "reason": reason,
        }

    for task in direct_tasks:
        if task.id in affected_tasks_map:
            continue
        # Invariant 4: If this task has an unconfirmed link, it must NOT be marked affected!
        if task.id in unconfirmed_task_ids:
            continue

        d_id = task.decision_id
        depth, d_nodes, d_edges, d_obj = affected_decisions[d_id]

        chain_nodes = list(d_nodes) + [("task", task.id)]
        chain_edges = list(d_edges) + [{
            "from_type": "decision",
            "from_id": f"D{d_id}",
            "to_type": "task",
            "to_id": f"T{task.id}",
            "relation": "implements",
        }]

        if root_premise:
            if depth == 1:
                reason = f"{trigger_prefix} > P{root_premise.id} supports D{d_obj.id} > D{d_obj.id} justifies T{task.id} ({task.title})"
            else:
                reason = f"{trigger_prefix} > P{root_premise.id} supports D{root_decision.id} > D{d_obj.id} depends on D{root_decision.id} > D{d_obj.id} justifies T{task.id} ({task.title})"
        else:
            if depth == 1:
                reason = f"{trigger_prefix} > D{d_obj.id} justifies T{task.id} ({task.title})"
            else:
                reason = f"{trigger_prefix} > D{d_obj.id} depends on D{root_decision.id} > D{d_obj.id} justifies T{task.id} ({task.title})"

        affected_tasks_map[task.id] = {
            "task": task,
            "depth": depth,
            "decision_id": d_id,
            "chain_nodes": chain_nodes,
            "chain_edges": chain_edges,
            "reason": reason,
        }

    # 4. Fetch all other tasks in the project to classify Unaffected & Needs Confirmation
    all_project_tasks = (
        db.query(Task)
        .join(Item, Task.item_id == Item.id)
        .join(Meeting, Item.meeting_id == Meeting.id)
        .filter(Meeting.project == project)
        .all()
    )

    affected_list: List[Dict[str, Any]] = []
    needs_confirmation_list: List[Dict[str, Any]] = []
    unaffected_list: List[Dict[str, Any]] = []

    # Format Affected List (sorted by depth ascending, then id ascending)
    sorted_affected = sorted(affected_tasks_map.values(), key=lambda x: (x["depth"], x["task"].id))
    for item_data in sorted_affected:
        t: Task = item_data["task"]
        affected_list.append({
            "id": t.id,
            "title": t.title,
            "status": t.status.value,
            "owner": t.owner.name if t.owner else "Unassigned",
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "estimate_hours": t.estimate_hours,
            "provisional": t.provisional,
            "depth": item_data["depth"],
            "decision_id": item_data["decision_id"],
            "chain_nodes": [
                {"type": n[0], "id": n[1], "label": f"{n[0][0].upper()}{n[1]}"}
                for n in item_data["chain_nodes"]
            ],
            "chain_edges": item_data["chain_edges"],
            "reason": item_data["reason"],
        })

    # Classify Remaining Project Tasks
    affected_ids = set(affected_tasks_map.keys())

    for t in all_project_tasks:
        if t.id in affected_ids:
            continue

        # Check if task has unconfirmed link
        if t.id in unconfirmed_task_ids:
            needs_confirmation_list.append({
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "owner": t.owner.name if t.owner else "Unassigned",
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "estimate_hours": t.estimate_hours,
                "reason": "needs confirmation, nothing changed",
                "status_badge": "needs_confirmation",
            })
            continue

        # Unaffected Task - compute reason via scope_overlap
        meeting_t = t.item.meeting if t.item else None
        task_region = (meeting_t.region if meeting_t else None)

        task_scope = {
            "project": project,
            "region": task_region,
        }
        root_scope = {
            "project": project,
            "region": root_region,
        }

        overlap = scope_overlap(task_scope, root_scope)
        if overlap == "disjoint":
            reason = f"scope differs: {task_region or 'Unknown'} vs {root_region or 'Unknown'}"
        else:
            reason = "no confirmed link to an affected decision"

        unaffected_list.append({
            "id": t.id,
            "title": t.title,
            "status": t.status.value,
            "owner": t.owner.name if t.owner else "Unassigned",
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "estimate_hours": t.estimate_hours,
            "region": task_region,
            "reason": reason,
        })

    # 5. Hours at Risk Calculation (Invariant 10: Never guess an estimate)
    hours_at_risk = 0.0
    unestimated_count = 0

    for item_data in sorted_affected:
        t: Task = item_data["task"]
        if t.status in (TaskStatus.open, TaskStatus.at_risk):
            if t.estimate_hours is not None:
                hours_at_risk += float(t.estimate_hours)
            else:
                unestimated_count += 1

    direct_count = sum(1 for x in affected_list if x["depth"] == 1)
    indirect_count = sum(1 for x in affected_list if x["depth"] > 1)

    return {
        "alert_id": alert.id if alert else None,
        "alert_kind": alert.kind.value if alert else ("premise_break" if root_premise else "superseded"),
        "verdict": alert.verdict if alert else "broken",
        "project": project,
        "trigger_evidence": {
            "speaker": speaker,
            "meeting_title": meeting_title,
            "meeting_date": meeting_date_str,
            "old_quote": old_quote,
            "new_quote": new_quote,
            "explanation": explanation,
        },
        "root_cause": {
            "type": "premise" if root_premise else "decision",
            "id": root_premise.id if root_premise else root_decision.id,
            "text": root_premise.text if root_premise else root_decision.text,
            "region": root_region,
        },
        "metrics": {
            "hours_at_risk": round(hours_at_risk, 1),
            "unestimated_count": unestimated_count,
            "total_affected": len(affected_list),
            "direct_affected": direct_count,
            "indirect_affected": indirect_count,
            "unaffected_count": len(unaffected_list),
            "needs_confirmation_count": len(needs_confirmation_list),
        },
        "affected": affected_list,
        "affected_decisions": [
            {
                "id": d_obj.id,
                "text": d_obj.text,
                "status": d_obj.status.value,
                "depth": depth,
            }
            for d_id, (depth, _, _, d_obj) in affected_decisions.items()
        ],
        "unaffected": unaffected_list,
        "needs_confirmation": needs_confirmation_list,
    }
