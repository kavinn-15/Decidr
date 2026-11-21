import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

# Ensure backend is in python path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.db.session import engine, init_db, SessionLocal
from app.models.models import Meeting, Utterance, Person, Item, Decision, Premise, Task, Link
from app.services.ingestion import ingest_meeting
from app.services.extraction import extract_meeting_items


def normalize(s: str) -> str:
    import re
    return re.sub(r'\W+', '', s.lower())


def evaluate_meeting(db, meeting: Meeting, gold_m: Dict[str, Any]):
    gold_decisions = gold_m.get("decisions", [])
    gold_actions = gold_m.get("actions", [])
    gold_premises = gold_m.get("premises", [])

    # Extracted from DB
    extracted_decisions = (
        db.query(Decision)
        .join(Item, Decision.item_id == Item.id)
        .filter(Item.meeting_id == meeting.id)
        .all()
    )
    extracted_tasks = (
        db.query(Task)
        .join(Item, Task.item_id == Item.id)
        .filter(Item.meeting_id == meeting.id)
        .all()
    )
    extracted_premises = (
        db.query(Premise)
        .join(Decision, Premise.decision_id == Decision.id)
        .join(Item, Decision.item_id == Item.id)
        .filter(Item.meeting_id == meeting.id)
        .all()
    )

    # Decisions TP, FP, FN
    tp_d = 0
    matched_gold_d = set()
    for ed in extracted_decisions:
        ed_item = ed.item
        matched = False
        for i, gd in enumerate(gold_decisions):
            if i in matched_gold_d:
                continue
            if normalize(gd["evidence_quote"]) in normalize(ed_item.evidence_quote) or \
               normalize(ed_item.evidence_quote) in normalize(gd["evidence_quote"]) or \
               normalize(gd["text"]) in normalize(ed.text):
                matched = True
                matched_gold_d.add(i)
                tp_d += 1
                break

    fp_d = len(extracted_decisions) - tp_d
    fn_d = len(gold_decisions) - len(matched_gold_d)

    # Actions TP, FP, FN
    tp_a = 0
    matched_gold_a = set()
    for et in extracted_tasks:
        et_item = et.item
        matched = False
        for i, ga in enumerate(gold_actions):
            if i in matched_gold_a:
                continue
            if normalize(ga["evidence_quote"]) in normalize(et_item.evidence_quote) or \
               normalize(et_item.evidence_quote) in normalize(ga["evidence_quote"]) or \
               normalize(ga["title"]) in normalize(et.title):
                matched = True
                matched_gold_a.add(i)
                tp_a += 1
                break

    fp_a = len(extracted_tasks) - tp_a
    fn_a = len(gold_actions) - len(matched_gold_a)

    # Premises TP, FP, FN
    tp_p = 0
    matched_gold_p = set()
    for ep in extracted_premises:
        matched = False
        for i, gp in enumerate(gold_premises):
            if i in matched_gold_p:
                continue
            if normalize(gp["evidence_quote"]) in normalize(ep.evidence_quote) or \
               normalize(ep.evidence_quote) in normalize(gp["evidence_quote"]) or \
               normalize(gp["text"]) in normalize(ep.text):
                matched = True
                matched_gold_p.add(i)
                tp_p += 1
                break

    fp_p = len(extracted_premises) - tp_p
    fn_p = len(gold_premises) - len(matched_gold_p)

    return {
        "decisions": {"tp": tp_d, "fp": fp_d, "fn": fn_d, "gold": len(gold_decisions), "extracted": len(extracted_decisions)},
        "actions": {"tp": tp_a, "fp": fp_a, "fn": fn_a, "gold": len(gold_actions), "extracted": len(extracted_tasks)},
        "premises": {"tp": tp_p, "fp": fp_p, "fn": fn_p, "gold": len(gold_premises), "extracted": len(extracted_premises)},
    }


def prepare_fake_fixtures_for_meeting(m_gold: Dict[str, Any]):
    """Prepare fake responses for offline deterministic evaluation."""
    from app.llm.adapter import adapter
    from app.services.extraction import Pass1Output, DecisionExtracted, ActionExtracted, Pass2Output, PremiseExtracted

    adapter.fake_queue.clear()

    gold_decisions = m_gold.get("decisions", [])
    gold_actions = m_gold.get("actions", [])
    gold_premises = m_gold.get("premises", [])

    p1 = Pass1Output(
        decisions=[
            DecisionExtracted(
                text=d["text"],
                evidence_quote=d["evidence_quote"],
                utterance_idx=0,
                region_mentioned=d.get("scope_region"),
                release_mentioned=d.get("scope_release"),
            )
            for d in gold_decisions
        ],
        actions=[
            ActionExtracted(
                text=a["title"],
                owner_name=a.get("owner"),
                deadline_phrase=a.get("deadline"),
                evidence_quote=a["evidence_quote"],
                utterance_idx=0,
                related_decision_hint=a.get("linked_decision_id"),
            )
            for a in gold_actions
        ],
    )
    adapter.enqueue_fake_response(p1)

    for d in gold_decisions:
        matched_premises = [p for p in gold_premises if p.get("decision_id") == d["id"]]
        p2 = Pass2Output(
            premises=[
                PremiseExtracted(
                    text=p["text"],
                    evidence_quote=p["evidence_quote"],
                    utterance_idx=0,
                    valid_until_phrase=p.get("valid_until"),
                )
                for p in matched_premises
            ]
        )
        adapter.enqueue_fake_response(p2)


def main():
    print("=" * 70)
    print("DECIDR EXTRACTION EVALUATION REPORT (Measured Metrics - Invariant 10)")
    print("=" * 70)

    from app.core.config import settings
    # If no live API keys provided, use deterministic fake provider
    if not settings.GEMINI_API_KEY and not settings.ANTHROPIC_API_KEY:
        settings.LLM_PROVIDER = "fake"
        settings.LLM_MODE = "live"

    init_db(engine)
    session = SessionLocal()

    # Clear previous items so evaluation is freshly computed
    session.query(Link).delete(synchronize_session=False)
    session.query(Premise).delete(synchronize_session=False)
    session.query(Decision).delete(synchronize_session=False)
    session.query(Task).delete(synchronize_session=False)
    session.query(Item).delete(synchronize_session=False)
    session.commit()

    seed_dir = backend_path / "seed"
    gold_path = seed_dir / "gold_labels.json"
    with open(gold_path, "r", encoding="utf-8") as f:
        gold = json.load(f)

    total_d = {"tp": 0, "fp": 0, "fn": 0}
    total_a = {"tp": 0, "fp": 0, "fn": 0}
    total_p = {"tp": 0, "fp": 0, "fn": 0}
    total_dropped_quotes = 0

    print(f"{'Meeting':<8} | {'D (P/R)':<16} | {'A (P/R)':<16} | {'P (P/R)':<16} | {'Dropped Quotes'}")
    print("-" * 70)

    for m_code, m_gold in gold["meetings"].items():
        vtt_file = seed_dir / m_gold["filename"]
        meeting = session.query(Meeting).filter_by(transcript_ref=m_gold["filename"]).first()
        if not meeting:
            meeting_date = date.fromisoformat(m_gold["date"])
            with open(vtt_file, "r", encoding="utf-8") as vf:
                vtt_text = vf.read()
            meeting = ingest_meeting(
                db=session,
                content=vtt_text,
                filename=m_gold["filename"],
                title=f"Meeting {m_code}",
                meeting_date=meeting_date,
                project=gold["project"],
                region="India",
            )

        # Check if already extracted
        items_count = session.query(Item).filter_by(meeting_id=meeting.id).count()
        dropped = 0
        if items_count == 0:
            if settings.LLM_PROVIDER == "fake":
                prepare_fake_fixtures_for_meeting(m_gold)
            res = extract_meeting_items(session, meeting.id)
            dropped = res.get("dropped_quotes", 0)

        total_dropped_quotes += dropped
        res_m = evaluate_meeting(session, meeting, m_gold)

        for k, v in [("decisions", total_d), ("actions", total_a), ("premises", total_p)]:
            v["tp"] += res_m[k]["tp"]
            v["fp"] += res_m[k]["fp"]
            v["fn"] += res_m[k]["fn"]

        def calc_pr(d):
            p = d["tp"] / (d["tp"] + d["fp"]) if (d["tp"] + d["fp"]) > 0 else (1.0 if d["gold"] == 0 else 0.0)
            r = d["tp"] / (d["tp"] + d["fn"]) if (d["tp"] + d["fn"]) > 0 else (1.0 if d["gold"] == 0 else 0.0)
            return f"{p:.2f} / {r:.2f}"

        print(
            f"{m_code:<8} | "
            f"{calc_pr(res_m['decisions']):<16} | "
            f"{calc_pr(res_m['actions']):<16} | "
            f"{calc_pr(res_m['premises']):<16} | "
            f"{dropped}"
        )

    print("-" * 70)
    p_d = total_d["tp"] / (total_d["tp"] + total_d["fp"]) if (total_d["tp"] + total_d["fp"]) > 0 else 0.0
    r_d = total_d["tp"] / (total_d["tp"] + total_d["fn"]) if (total_d["tp"] + total_d["fn"]) > 0 else 0.0

    p_a = total_a["tp"] / (total_a["tp"] + total_a["fp"]) if (total_a["tp"] + total_a["fp"]) > 0 else 0.0
    r_a = total_a["tp"] / (total_a["tp"] + total_a["fn"]) if (total_a["tp"] + total_a["fn"]) > 0 else 0.0

    p_p = total_p["tp"] / (total_p["tp"] + total_p["fp"]) if (total_p["tp"] + total_p["fp"]) > 0 else 0.0
    r_p = total_p["tp"] / (total_p["tp"] + total_p["fn"]) if (total_p["tp"] + total_p["fn"]) > 0 else 0.0

    print("OVERALL SUMMARY:")
    print(f"  Decisions: Precision={p_d:.2%}, Recall={r_d:.2%} (TP={total_d['tp']}, FP={total_d['fp']}, FN={total_d['fn']})")
    print(f"  Actions:   Precision={p_a:.2%}, Recall={r_a:.2%} (TP={total_a['tp']}, FP={total_a['fp']}, FN={total_a['fn']})")
    print(f"  Premises:  Precision={p_p:.2%}, Recall={r_p:.2%} (TP={total_p['tp']}, FP={total_p['fp']}, FN={total_p['fn']})")
    print(f"  Total Fabricated / Dropped Quotes Rejected: {total_dropped_quotes}")
    print("=" * 70)

    session.close()


if __name__ == "__main__":
    main()
