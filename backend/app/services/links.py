from typing import Any, Optional, Union, List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.models.models import Link
from app.models.enums import LinkRelation
from app.services.audit import log


def create_link(
    db: Session,
    source_type: str,
    source_id: int,
    target_type: str,
    target_id: int,
    relation: Union[LinkRelation, str],
    confirmed: bool = False,
    confidence: float = 1.0,
    rationale: Optional[str] = None,
    actor: str = "system",
) -> Link:
    """
    Creates or updates a link between two graph nodes.
    Invariant 4: candidate links start unconfirmed by default until explicitly reviewed.
    """
    if isinstance(relation, str):
        relation = LinkRelation(relation)

    existing = (
        db.query(Link)
        .filter(
            Link.source_type == source_type,
            Link.source_id == source_id,
            Link.target_type == target_type,
            Link.target_id == target_id,
            Link.relation == relation,
        )
        .first()
    )
    if existing:
        before = {
            "confirmed": existing.confirmed,
            "confidence": existing.confidence,
            "rationale": existing.rationale,
        }
        existing.confirmed = confirmed
        existing.confidence = confidence
        existing.rationale = rationale
        db.flush()
        log(
            actor=actor,
            action="update_link",
            entity_type="link",
            entity_id=existing.id,
            before=before,
            after={
                "confirmed": existing.confirmed,
                "confidence": existing.confidence,
                "rationale": existing.rationale,
            },
            db=db,
        )
        return existing

    link = Link(
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relation=relation,
        confirmed=confirmed,
        confidence=confidence,
        rationale=rationale,
    )
    db.add(link)
    db.flush()

    log(
        actor=actor,
        action="create_link",
        entity_type="link",
        entity_id=link.id,
        before=None,
        after={
            "source_type": link.source_type,
            "source_id": link.source_id,
            "target_type": link.target_type,
            "target_id": link.target_id,
            "relation": link.relation.value,
            "confirmed": link.confirmed,
            "confidence": link.confidence,
        },
        db=db,
    )
    return link


def confirm_link(
    db: Session,
    link_id: int,
    actor: str = "reviewer",
) -> Link:
    """
    Confirms a link in the graph and writes an audit log.
    """
    link = db.get(Link, link_id)
    if not link:
        raise ValueError(f"Link {link_id} not found")

    before = {"confirmed": link.confirmed}
    link.confirmed = True
    db.flush()

    log(
        actor=actor,
        action="confirm_link",
        entity_type="link",
        entity_id=link.id,
        before=before,
        after={"confirmed": link.confirmed},
        db=db,
    )
    return link


def reject_link(
    db: Session,
    link_id: int,
    actor: str = "reviewer",
) -> Link:
    """
    Rejects/deconfirms a link in the graph and writes an audit log.
    """
    link = db.get(Link, link_id)
    if not link:
        raise ValueError(f"Link {link_id} not found")

    before = {"confirmed": link.confirmed}
    link.confirmed = False
    db.flush()

    log(
        actor=actor,
        action="reject_link",
        entity_type="link",
        entity_id=link.id,
        before=before,
        after={"confirmed": link.confirmed},
        db=db,
    )
    return link


def _normalize_node(node: Any) -> Tuple[str, int]:
    """
    Normalizes a node input into a (node_type, node_id) tuple.
    Accepts (type, id), dict, or ORM model instances.
    """
    if isinstance(node, (tuple, list)) and len(node) == 2:
        return str(node[0]), int(node[1])
    if isinstance(node, dict):
        t = node.get("type") or node.get("node_type")
        i = node.get("id") or node.get("node_id")
        if t is not None and i is not None:
            return str(t), int(i)
    if hasattr(node, "__tablename__") and hasattr(node, "id"):
        tbl = node.__tablename__
        if tbl.endswith("s"):
            tbl = tbl[:-1]
        return tbl, int(node.id)
    if isinstance(node, str) and ":" in node:
        parts = node.split(":", 1)
        return parts[0], int(parts[1])
    raise ValueError(f"Cannot parse node specification: {node}")


def neighbors(
    db: Session,
    node: Any,
    relations: Optional[List[Union[LinkRelation, str]]] = None,
    confirmed_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieves neighboring nodes in the decision/task knowledge graph.
    Invariant 4: Graph queries must ignore unconfirmed links by default (confirmed_only=True).
    """
    node_type, node_id = _normalize_node(node)

    query = db.query(Link).filter(
        or_(
            and_(Link.source_type == node_type, Link.source_id == node_id),
            and_(Link.target_type == node_type, Link.target_id == node_id),
        )
    )

    if confirmed_only:
        query = query.filter(Link.confirmed == True)  # noqa: E712

    if relations:
        rel_enums = [
            r if isinstance(r, LinkRelation) else LinkRelation(r)
            for r in relations
        ]
        query = query.filter(Link.relation.in_(rel_enums))

    links = query.all()

    results: List[Dict[str, Any]] = []
    for link in links:
        if link.source_type == node_type and link.source_id == node_id:
            results.append({
                "node_type": link.target_type,
                "node_id": link.target_id,
                "direction": "outgoing",
                "relation": link.relation.value,
                "confirmed": link.confirmed,
                "confidence": link.confidence,
                "rationale": link.rationale,
                "link_id": link.id,
            })
        else:
            results.append({
                "node_type": link.source_type,
                "node_id": link.source_id,
                "direction": "incoming",
                "relation": link.relation.value,
                "confirmed": link.confirmed,
                "confidence": link.confidence,
                "rationale": link.rationale,
                "link_id": link.id,
            })

    return results
