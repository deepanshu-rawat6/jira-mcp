"""Confluence MCP tools — registered onto the FastMCP server via register().

Safety tiers
------------
🟢 Auto-approved : confluence_search, confluence_list_spaces, confluence_get_page,
                   confluence_add_comment
⚠️  WRITE        : confluence_create_page
🔴 DESTRUCTIVE   : confluence_update_page
"""

import re
from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    """Remove HTML/XML tags and decode common entities."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    # Collapse whitespace
    return re.sub(r"\s{2,}", " ", text).strip()


def _text_to_storage(text: str) -> str:
    """Convert plain text to minimal Confluence storage format."""
    paragraphs = "".join(
        f"<p>{line or '&#160;'}</p>" for line in text.splitlines()
    )
    return paragraphs or f"<p>{text}</p>"


def _text_to_adf(text: str) -> dict:
    """Wrap plain text in a minimal ADF document."""
    paragraphs = [
        {"type": "paragraph", "content": [{"type": "text", "text": line or " "}]}
        for line in text.splitlines()
    ] or [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]
    return {"version": 1, "type": "doc", "content": paragraphs}


# ── Tool registration ──────────────────────────────────────────────────────────

def register(mcp: "FastMCP") -> None:
    """Register all Confluence tools onto *mcp*."""

    # ── READ tools ────────────────────────────────────────────────────────────

    @mcp.tool()
    async def confluence_search(cql: str, limit: int = 20, ctx: Context = None) -> str:
        """Search Confluence content using CQL (Confluence Query Language).

        Args:
            cql: CQL query string.
                 Examples: 'space = ENG AND title ~ "onboarding"'
                           'type = page AND text ~ "deployment"'
            limit: Maximum number of results (default 20).

        Returns:
            Formatted list of matching pages with title, space, and URL.
        """
        app = ctx.request_context.lifespan_context
        data = await app.confluence.get(
            "/wiki/rest/api/content/search",
            params={"cql": cql, "limit": min(limit, 50), "expand": "space,version"},
        )
        results = data.get("results", [])
        if not results:
            return "No Confluence pages found."
        lines = [f"Found {data.get('totalSize', len(results))} result(s) (showing {len(results)}):"]
        base = app.confluence._base_url
        for page in results:
            space = page.get("space", {}).get("key", "?")
            modified = page.get("version", {}).get("when", "")[:10]
            lines.append(
                f"  [{space}] {page['title']}\n"
                f"    ID={page['id']}  Modified={modified}\n"
                f"    URL={base}/wiki{page.get('_links', {}).get('webui', '')}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def confluence_list_spaces(limit: int = 25, ctx: Context = None) -> str:
        """List all Confluence spaces accessible to the authenticated user.

        Args:
            limit: Maximum number of spaces to return (default 25).

        Returns:
            Formatted list of spaces with key, name, type, and URL.
        """
        app = ctx.request_context.lifespan_context
        data = await app.confluence.get(
            "/wiki/api/v2/spaces",
            params={"limit": min(limit, 50)},
        )
        spaces = data.get("results", [])
        if not spaces:
            return "No spaces found."
        base = app.confluence._base_url
        lines = [f"Confluence spaces ({len(spaces)}):"]
        for s in spaces:
            lines.append(
                f"  [{s.get('key', '?')}] {s['name']}  type={s.get('type', '?')}\n"
                f"    ID={s['id']}  URL={base}/wiki{s.get('_links', {}).get('webui', '')}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def confluence_get_page(page_id: str, ctx: Context = None) -> str:
        """Get the content of a Confluence page by its ID.

        Args:
            page_id: Numeric Confluence page ID (visible in the page URL).

        Returns:
            Page title, space, metadata, and body as readable plain text.
        """
        app = ctx.request_context.lifespan_context
        data = await app.confluence.get(
            f"/wiki/api/v2/pages/{page_id}",
            params={"body-format": "storage"},
        )
        body_html = (data.get("body") or {}).get("storage", {}).get("value", "")
        body_text = _strip_html(body_html)
        base = app.confluence._base_url
        web_url = base + "/wiki" + (data.get("_links") or {}).get("webui", "")
        return (
            f"Page: {data['title']} (ID={data['id']})\n"
            f"Space ID: {data.get('spaceId', '?')}\n"
            f"Version:  {(data.get('version') or {}).get('number', '?')}\n"
            f"URL:      {web_url}\n"
            f"Body:\n{body_text or '(empty)'}"
        )

    # ── AUTO-APPROVED write tool ───────────────────────────────────────────────

    @mcp.tool()
    async def confluence_add_comment(
        page_id: str, comment: str, ctx: Context = None
    ) -> str:
        """Add a footer comment to a Confluence page.

        Args:
            page_id: Numeric Confluence page ID.
            comment: Comment body (plain text).

        Returns:
            Confirmation with the new comment ID.
        """
        app = ctx.request_context.lifespan_context
        result = await app.confluence.post(
            f"/wiki/api/v2/pages/{page_id}/footer-comments",
            body={"body": {"representation": "atlas_doc_format", "value": _text_to_adf(comment)}},
        )
        return f"Comment added to page {page_id} (id={result.get('id', '?')})."

    # ── MEDIUM-RISK write tool (⚠️ WRITE) ─────────────────────────────────────

    @mcp.tool()
    async def confluence_create_page(
        space_id: str,
        title: str,
        body: str,
        parent_id: str | None = None,
        ctx: Context = None,
    ) -> str:
        """⚠️ WRITE: Create a new Confluence page.

        The body is plain text and will be converted to Confluence storage format.
        Confirm space ID and title before calling.

        Args:
            space_id: Numeric Confluence space ID (use confluence_list_spaces to find it).
            title: Page title.
            body: Page content as plain text.
            parent_id: Optional parent page ID to nest this page under.

        Returns:
            New page ID and URL.
        """
        app = ctx.request_context.lifespan_context
        payload: dict = {
            "spaceId": space_id,
            "title": title,
            "body": {
                "representation": "storage",
                "value": _text_to_storage(body),
            },
        }
        if parent_id:
            payload["parentId"] = parent_id

        result = await app.confluence.post("/wiki/api/v2/pages", body=payload)
        base = app.confluence._base_url
        web_url = base + "/wiki" + (result.get("_links") or {}).get("webui", "")
        return f"Created page '{title}' (ID={result['id']}): {web_url}"

    # ── HIGH-RISK tool (🔴 DESTRUCTIVE) ───────────────────────────────────────

    @mcp.tool()
    async def confluence_update_page(
        page_id: str,
        title: str,
        body: str,
        version_message: str | None = None,
        ctx: Context = None,
    ) -> str:
        """🔴 DESTRUCTIVE: Replace the entire content of a Confluence page.

        This overwrites all existing page content. Always get explicit user
        confirmation including the page title before calling this tool.

        Args:
            page_id: Numeric Confluence page ID.
            title: New (or existing) page title.
            body: New page content as plain text — replaces current content entirely.
            version_message: Optional message describing the change (shown in page history).

        Returns:
            Confirmation with the updated page URL.
        """
        app = ctx.request_context.lifespan_context

        # Fetch current version number — required by the API
        current = await app.confluence.get(f"/wiki/api/v2/pages/{page_id}")
        current_version: int = (current.get("version") or {}).get("number", 0)

        payload: dict = {
            "id": page_id,
            "title": title,
            "version": {"number": current_version + 1},
            "body": {
                "representation": "storage",
                "value": _text_to_storage(body),
            },
        }
        if version_message:
            payload["version"]["message"] = version_message

        result = await app.confluence.put(f"/wiki/api/v2/pages/{page_id}", body=payload)
        base = app.confluence._base_url
        web_url = base + "/wiki" + (result.get("_links") or {}).get("webui", "")
        return f"Updated page '{title}' (ID={page_id}) to version {current_version + 1}: {web_url}"
