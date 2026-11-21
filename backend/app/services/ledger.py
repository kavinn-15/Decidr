import re
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from sqlalchemy.orm import Session, selectinload
from rank_bm25 import BM25Okapi

from app.models.models import Decision, Premise
from app.models.enums import DecisionStatus


def _extract_scope_fields(
    obj: Any,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[date], Optional[date]]:
    """
    Extracts project, region, release, effective_from/valid_from, and
    effective_to/valid_until from an ORM model or dictionary.
    """
    if isinstance(obj, dict):
        proj = obj.get("scope_project") or obj.get("project")
        reg = obj.get("scope_region") or obj.get("region")
        rel = obj.get("scope_release") or obj.get("release")
        eff_from = obj.get("effective_from") or obj.get("valid_from")
        eff_to = obj.get("effective_to") or obj.get("valid_until")
    else:
        proj = getattr(obj, "scope_project", None) or getattr(obj, "project", None)
        reg = getattr(obj, "scope_region", None) or getattr(obj, "region", None)
        rel = getattr(obj, "scope_release", None) or getattr(obj, "release", None)
        eff_from = getattr(obj, "effective_from", None) or getattr(obj, "valid_from", None)
        eff_to = getattr(obj, "effective_to", None) or getattr(obj, "valid_until", None)

    # Normalize dates if provided as strings or datetimes
    if isinstance(eff_from, str):
        try:
            eff_from = date.fromisoformat(eff_from)
        except ValueError:
            eff_from = None
    elif isinstance(eff_from, datetime):
        eff_from = eff_from.date()

    if isinstance(eff_to, str):
        try:
            eff_to = date.fromisoformat(eff_to)
        except ValueError:
            eff_to = None
    elif isinstance(eff_to, datetime):
        eff_to = eff_to.date()

    proj = proj.strip() if isinstance(proj, str) and proj.strip() else (proj if proj is not None and not isinstance(proj, str) else None)
    reg = reg.strip() if isinstance(reg, str) and reg.strip() else None
    rel = rel.strip() if isinstance(rel, str) and rel.strip() else None

    return proj, reg, rel, eff_from, eff_to


def scope_overlap(a: Any, b: Any) -> Literal["overlap", "disjoint", "unknown"]:
    """
    Compares project, region, release, and effective dates of two scoped records to determine
    whether their operational spheres overlap, are provably disjoint, or are unknown.

    Rules:
    1. Project Disjointness:
       - If both records define a project and they differ (case-insensitive),
         the scopes are "disjoint".
       - If either record lacks a project context, the relationship is "unknown".

    2. Region Disjointness:
       - If both records define a non-null region and they differ (case-insensitive),
         the scopes are "disjoint" (e.g., India vs Europe).

    3. Release Disjointness:
       - If both records define a non-null release and they differ (case-insensitive),
         the scopes are "disjoint" (e.g., v1.0 vs v2.0).

    4. Temporal Disjointness:
       - If both records define effective date boundaries and their intervals do not intersect
         (i.e., a.effective_to < b.effective_from or b.effective_to < a.effective_from),
         the scopes are "disjoint".

    5. Identical Scope (Overlap):
       - If both records share the same project, identical regions, identical releases,
         and intersecting date ranges, they are "overlap".

    6. One-Side-Null Scope (Overlap):
       - If within the same project, one record has a null region (or null release)
         representing an unconstrained global / project-wide scope, it encompasses the
         specific regional/release scope, yielding "overlap".

    7. Cross-Unspecified Ambiguity (Unknown):
       - If record A specifies a region but has a null release, while record B specifies
         a release but has a null region (cross-unspecified dimensions), their intersection
         cannot be verified without deployment mapping, yielding "unknown".
    """
    proj_a, reg_a, rel_a, from_a, to_a = _extract_scope_fields(a)
    proj_b, reg_b, rel_b, from_b, to_b = _extract_scope_fields(b)

    # Rule 1: Project
    if proj_a and proj_b and proj_a.lower() != proj_b.lower():
        return "disjoint"
    if not proj_a or not proj_b:
        return "unknown"

    # Rule 2: Region
    if reg_a and reg_b and reg_a.lower() != reg_b.lower():
        return "disjoint"

    # Rule 3: Release
    if rel_a and rel_b and rel_a.lower() != rel_b.lower():
        return "disjoint"

    # Rule 4: Dates
    if to_a and from_b and to_a < from_b:
        return "disjoint"
    if to_b and from_a and to_b < from_a:
        return "disjoint"

    # Rule 7: Cross-unspecified ambiguity
    if (reg_a and not reg_b and not rel_a and rel_b) or (not reg_a and reg_b and rel_a and not rel_b):
        return "unknown"

    # Rule 5 & 6: Identical scope or one side null/global
    return "overlap"


def _tokenize(text: str) -> List[str]:
    """Basic alphanumeric lower-cased tokenizer for BM25 ranking."""
    return [w.lower() for w in re.findall(r"\w+", text)]


def search(
    db: Session,
    project: Optional[str] = None,
    text: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    status: Optional[Union[DecisionStatus, str]] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Searches decisions in the ledger: applies scope and status filters first,
    then applies BM25 (rank_bm25) over decision text plus premise text,
    returning scored hits.
    """
    query = db.query(Decision).options(selectinload(Decision.premises))

    if project:
        query = query.filter(Decision.scope_project == project)

    if status:
        if isinstance(status, str):
            status = DecisionStatus(status)
        query = query.filter(Decision.status == status)

    candidates: List[Decision] = query.all()

    # Scope filter first (using scope_overlap)
    if scope:
        candidates = [
            c for c in candidates
            if scope_overlap(c, scope) != "disjoint"
        ]

    if not candidates:
        return []

    # If text query is provided, rank via BM25
    if text and text.strip():
        query_tokens = _tokenize(text)
        if not query_tokens:
            return [
                {"decision": c, "score": 0.0, "premises": c.premises}
                for c in candidates[:limit]
            ]

        corpus = []
        for d in candidates:
            premise_text = " ".join(p.text for p in d.premises)
            combined = f"{d.text} {premise_text}"
            doc_tokens = _tokenize(combined)
            corpus.append(doc_tokens if doc_tokens else [""])

        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)

        scored = list(zip(candidates, scores))
        # Sort descending by BM25 score
        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                "decision": d,
                "score": float(score),
                "premises": d.premises,
            }
            for d, score in scored[:limit]
        ]

    # Without text, sort by decision ID descending
    candidates.sort(key=lambda d: d.id, reverse=True)
    return [
        {
            "decision": d,
            "score": 0.0,
            "premises": d.premises,
        }
        for d in candidates[:limit]
    ]
