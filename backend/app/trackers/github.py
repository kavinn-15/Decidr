import httpx
from typing import Optional, Any
from app.core.config import settings
from app.trackers.base import BaseTracker


class GitHubTracker(BaseTracker):
    """
    GitHub issue tracker using the GitHub REST API via httpx.
    Embeds `<!-- decidr:KEY -->` in the issue body to enable deterministic idempotency.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ):
        self.token = token or settings.GITHUB_TOKEN
        self.repo = repo or settings.GITHUB_REPO
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return httpx.Client(
            base_url="https://api.github.com",
            headers=headers,
            timeout=10.0,
        )

    def find_by_key(self, idempotency_key: str) -> Optional[str]:
        if not idempotency_key or not self.repo:
            return None

        marker = f"<!-- decidr:{idempotency_key} -->"
        client = self._get_client()
        should_close = self._client is None
        try:
            # 1. Direct issues listing with label decidr
            list_resp = client.get(
                f"/repos/{self.repo}/issues",
                params={"state": "all", "labels": "decidr", "per_page": 100},
            )
            if list_resp.status_code == 200:
                issues = list_resp.json()
                if isinstance(issues, list):
                    for issue in issues:
                        body = issue.get("body") or ""
                        if marker in body:
                            return str(issue["number"])

            # 2. Search API query
            search_query = f'repo:{self.repo} "decidr:{idempotency_key}"'
            search_resp = client.get("/search/issues", params={"q": search_query})
            if search_resp.status_code == 200:
                items = search_resp.json().get("items", [])
                for item in items:
                    body = item.get("body") or ""
                    if marker in body:
                        return str(item["number"])

            return None
        except Exception:
            return None
        finally:
            if should_close:
                client.close()

    def create_issue(
        self,
        title: str,
        body: str,
        assignee: Optional[str] = None,
        due_date: Optional[str] = None,
        labels: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, str]:
        if not self.repo:
            raise ValueError("GITHUB_REPO is not configured for GitHubTracker")

        # Idempotency check: if issue already exists with this key, return it
        if idempotency_key:
            existing = self.find_by_key(idempotency_key)
            if existing:
                return {
                    "ref": existing,
                    "url": f"https://github.com/{self.repo}/issues/{existing}",
                }

        marker = f"\n\n<!-- decidr:{idempotency_key} -->" if idempotency_key else ""
        due_note = f"\n**Due Date**: {due_date}" if due_date else ""
        full_body = (body or "") + due_note + marker

        combined_labels = list(set(["decidr"] + (labels or [])))
        payload: dict[str, Any] = {
            "title": title,
            "body": full_body.strip(),
            "labels": combined_labels,
        }
        if assignee:
            payload["assignees"] = [assignee]

        client = self._get_client()
        should_close = self._client is None
        try:
            resp = client.post(f"/repos/{self.repo}/issues", json=payload)
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"GitHub API error creating issue: {resp.status_code} {resp.text}"
                )
            data = resp.json()
            ref_num = str(data["number"])
            issue_url = data.get("html_url", f"https://github.com/{self.repo}/issues/{ref_num}")
            return {"ref": ref_num, "url": issue_url}
        finally:
            if should_close:
                client.close()

    def add_comment(self, ref: str, text: str) -> None:
        if not self.repo:
            raise ValueError("GITHUB_REPO is not configured")

        client = self._get_client()
        should_close = self._client is None
        try:
            resp = client.post(f"/repos/{self.repo}/issues/{ref}/comments", json={"body": text})
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"GitHub API error adding comment to issue #{ref}: {resp.status_code} {resp.text}"
                )
        finally:
            if should_close:
                client.close()

    def reopen(self, ref: str) -> None:
        if not self.repo:
            raise ValueError("GITHUB_REPO is not configured")

        client = self._get_client()
        should_close = self._client is None
        try:
            resp = client.patch(f"/repos/{self.repo}/issues/{ref}", json={"state": "open"})
            if resp.status_code != 200:
                raise RuntimeError(
                    f"GitHub API error reopening issue #{ref}: {resp.status_code} {resp.text}"
                )
        finally:
            if should_close:
                client.close()

    def cancel(self, ref: str) -> None:
        if not self.repo:
            raise ValueError("GITHUB_REPO is not configured")

        client = self._get_client()
        should_close = self._client is None
        try:
            resp = client.patch(
                f"/repos/{self.repo}/issues/{ref}",
                json={"state": "closed", "state_reason": "not_planned"},
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"GitHub API error cancelling issue #{ref}: {resp.status_code} {resp.text}"
                )
        finally:
            if should_close:
                client.close()
