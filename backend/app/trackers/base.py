from abc import ABC, abstractmethod
from typing import Optional


class BaseTracker(ABC):
    """
    Abstract interface for issue trackers (MockTracker, GitHubTracker, etc.).
    """

    @abstractmethod
    def create_issue(
        self,
        title: str,
        body: str,
        assignee: Optional[str] = None,
        due_date: Optional[str] = None,
        labels: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Creates an issue in the issue tracker.
        Returns a dict: {"ref": "<issue_ref>", "url": "<issue_url>"}
        """
        pass

    @abstractmethod
    def add_comment(self, ref: str, text: str) -> None:
        """
        Adds a comment to an existing issue.
        """
        pass

    @abstractmethod
    def reopen(self, ref: str) -> None:
        """
        Reopens a closed/cancelled issue.
        """
        pass

    @abstractmethod
    def cancel(self, ref: str) -> None:
        """
        Cancels or closes an issue.
        """
        pass

    @abstractmethod
    def find_by_key(self, idempotency_key: str) -> Optional[str]:
        """
        Finds an existing issue ref by its idempotency_key, or returns None.
        """
        pass
