import json
import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from app.models.models import Person, Meeting, Utterance
from scripts.seed import seed_database


def test_seed_verbatim_quotes_match():
    """
    Invariant 6: Every evidence_quote must be an exact substring of the transcript.
    Assert that all gold label quotes are exact substrings of the corresponding VTT transcripts.
    """
    seed_dir = Path(__file__).resolve().parent.parent / "seed"
    gold_path = seed_dir / "gold_labels.json"
    with open(gold_path, "r", encoding="utf-8") as f:
        gold = json.load(f)

    for m_key, m_data in gold["meetings"].items():
        vtt_path = seed_dir / m_data["filename"]
        assert vtt_path.exists(), f"VTT file {m_data['filename']} not found"
        with open(vtt_path, "r", encoding="utf-8") as vf:
            vtt_text = vf.read()

        # Check decisions
        for d in m_data.get("decisions", []):
            quote = d.get("evidence_quote")
            if quote:
                assert quote in vtt_text, f"Decision quote '{quote}' not found in {m_data['filename']}"

        # Check premises
        for p in m_data.get("premises", []):
            quote = p.get("evidence_quote")
            if quote:
                assert quote in vtt_text, f"Premise quote '{quote}' not found in {m_data['filename']}"

        # Check actions
        for a in m_data.get("actions", []):
            quote = a.get("evidence_quote")
            if quote:
                assert quote in vtt_text, f"Action quote '{quote}' not found in {m_data['filename']}"

        # Check expected alerts quotes
        for alert in m_data.get("expected_alerts", []):
            old_quote = alert.get("old_quote")
            new_quote = alert.get("new_quote")
            if old_quote:
                # old_quote might be from an earlier meeting, check all meetings
                found = any(old_quote in (seed_dir / other_m["filename"]).read_text(encoding="utf-8") for other_m in gold["meetings"].values())
                assert found, f"Alert old_quote '{old_quote}' not found in any transcript"
            if new_quote:
                assert new_quote in vtt_text, f"Alert new_quote '{new_quote}' not found in {m_data['filename']}"


def test_heldout_verbatim_quotes_match():
    """
    Assert that all held-out gold label quotes are exact substrings of their VTT files.
    """
    heldout_dir = Path(__file__).resolve().parent.parent / "seed" / "heldout"
    gold_path = heldout_dir / "gold_labels_heldout.json"
    with open(gold_path, "r", encoding="utf-8") as f:
        gold = json.load(f)

    for h_key, h_data in gold["meetings"].items():
        vtt_path = heldout_dir / h_data["filename"]
        assert vtt_path.exists()
        with open(vtt_path, "r", encoding="utf-8") as vf:
            vtt_text = vf.read()

        for d in h_data.get("decisions", []):
            assert d["evidence_quote"] in vtt_text

        for p in h_data.get("premises", []):
            assert p["evidence_quote"] in vtt_text

        for a in h_data.get("actions", []):
            assert a["evidence_quote"] in vtt_text

        for alert in h_data.get("expected_alerts", []):
            if alert.get("old_quote"):
                found = any(alert["old_quote"] in (heldout_dir / other_h["filename"]).read_text(encoding="utf-8") for other_h in gold["meetings"].values())
                assert found
            if alert.get("new_quote"):
                assert alert["new_quote"] in vtt_text


def test_seed_database_loads_records():
    """
    Assert that the seed database populates people and meeting utterances without labels.
    """
    from app.db.session import SessionLocal
    seed_database()
    with SessionLocal() as session:
        people_count = session.query(Person).count()
        meeting_count = session.query(Meeting).count()
        utterance_count = session.query(Utterance).count()

        assert people_count >= 6
        assert meeting_count >= 4
        assert utterance_count >= 50
