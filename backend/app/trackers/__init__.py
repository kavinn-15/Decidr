from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.trackers.base import BaseTracker
from app.trackers.mock import MockTracker
from app.trackers.github import GitHubTracker


def get_tracker(
    tracker_type: Optional[str] = None,
    db: Optional[Session] = None,
) -> BaseTracker:
    chosen = (tracker_type or settings.TRACKER or "mock").lower()
    if chosen == "github":
        return GitHubTracker()
    return MockTracker(db=db)


__all__ = ["BaseTracker", "MockTracker", "GitHubTracker", "get_tracker"]
