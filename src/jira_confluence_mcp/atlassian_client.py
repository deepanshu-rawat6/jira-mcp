"""Async HTTP client for Atlassian Cloud REST APIs.

Handles Basic Auth (email + API token), JSON serialisation, and maps
HTTP error codes to human-readable messages via AtlassianAPIError.
"""

import base64
from typing import Any

import httpx


class AtlassianAPIError(Exception):
    """Raised when an Atlassian API call returns a non-2xx status."""

    def __init__(self, status_code: int, message: str, body: str = "") -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message)


_STATUS_MESSAGES: dict[int, str] = {
    401: "Authentication failed — check JIRA_USERNAME and JIRA_API_TOKEN.",
    403: "Permission denied — your account lacks access to this resource.",
    404: "Resource not found — verify the issue key, page ID, or project key.",
    429: "Rate limit exceeded — slow down requests.",
}


class AtlassianClient:
    """Thin async wrapper around httpx for Jira / Confluence REST APIs.

    Args:
        base_url: Root URL, e.g. ``https://company.atlassian.net``.
        username: Atlassian account email.
        api_token: API token from id.atlassian.com.
    """

    def __init__(self, base_url: str, username: str, api_token: str) -> None:
        credentials = base64.b64encode(f"{username}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._base_url = base_url.rstrip("/")

    def _raise(self, exc: httpx.HTTPStatusError) -> None:
        code = exc.response.status_code
        body = exc.response.text
        msg = _STATUS_MESSAGES.get(code, f"HTTP {code}: {exc.response.reason_phrase}")
        raise AtlassianAPIError(code, msg, body) from exc

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a GET request and return parsed JSON."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self._base_url}{path}", headers=self._headers, params=params
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._raise(exc)
        return resp.json()

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        """Perform a POST request and return parsed JSON (or {} for 204)."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self._base_url}{path}", headers=self._headers, json=body
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._raise(exc)
        return resp.json() if resp.content else {}

    async def put(self, path: str, body: dict[str, Any]) -> Any:
        """Perform a PUT request and return parsed JSON (or {} for 204)."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.put(
                    f"{self._base_url}{path}", headers=self._headers, json=body
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._raise(exc)
        return resp.json() if resp.content else {}
