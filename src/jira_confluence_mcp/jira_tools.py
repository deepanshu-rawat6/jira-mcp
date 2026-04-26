"""Jira MCP tools — registered onto the FastMCP server via register().

Safety tiers
------------
🟢 Auto-approved : jira_search, jira_get_issue, jira_add_comment, jira_add_label
⚠️  WRITE        : jira_create_issue, jira_update_issue, jira_link_issues
🔴 DESTRUCTIVE   : jira_transition_issue
"""

from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# ── ADF helper ────────────────────────────────────────────────────────────────

def _extract_text(node: dict | None) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    if not node:
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_extract_text(child) for child in node.get("content", [])]
    # Add newline after block-level nodes
    sep = "\n" if node.get("type") in {"paragraph", "heading", "listItem", "bulletList", "orderedList"} else ""
    return sep.join(parts)


def _text_to_adf(text: str) -> dict:
    """Wrap plain text in a minimal ADF document (one paragraph per line)."""
    paragraphs = [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": line or " "}],
        }
        for line in text.splitlines()
    ] or [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]
    return {"version": 1, "type": "doc", "content": paragraphs}


# ── Tool registration ──────────────────────────────────────────────────────────

def register(mcp: "FastMCP") -> None:
    """Register all Jira tools onto *mcp*."""

    # ── READ tools ────────────────────────────────────────────────────────────

    @mcp.tool()
    async def jira_search(jql: str, max_results: int = 20, ctx: Context = None) -> str:
        """Search Jira issues using JQL (Jira Query Language).

        Args:
            jql: JQL query string.
                 Examples: 'project = ENG AND status = "In Progress"'
                           'assignee = currentUser() ORDER BY updated DESC'
            max_results: Maximum number of issues to return (default 20, max 50).

        Returns:
            Formatted list of matching issues with key, summary, status, and assignee.
        """
        app = ctx.request_context.lifespan_context
        data = await app.jira.get(
            "/rest/api/3/search",
            params={
                "jql": jql,
                "maxResults": min(max_results, 50),
                "fields": "summary,status,assignee,priority,labels",
            },
        )
        issues = data.get("issues", [])
        if not issues:
            return "No issues found."
        lines = [f"Found {data['total']} issue(s) (showing {len(issues)}):"]
        for issue in issues:
            f = issue["fields"]
            assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
            priority = (f.get("priority") or {}).get("name", "—")
            lines.append(
                f"  {issue['key']}: {f['summary']}\n"
                f"    Status={f['status']['name']}  Assignee={assignee}  Priority={priority}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def jira_get_issue(issue_key: str, ctx: Context = None) -> str:
        """Get full details of a Jira issue by its key.

        Args:
            issue_key: Jira issue key, e.g. ``ENG-123``.

        Returns:
            Formatted issue details including summary, status, assignee, priority,
            labels, description, and the three most recent comments.
        """
        app = ctx.request_context.lifespan_context
        data = await app.jira.get(
            f"/rest/api/3/issue/{issue_key}",
            params={
                "fields": "summary,description,status,assignee,priority,labels,comment,issuetype,created,updated"
            },
        )
        f = data["fields"]
        comments = (f.get("comment") or {}).get("comments", [])[-3:]
        comment_lines = "\n".join(
            f"  [{c['author']['displayName']}]: {_extract_text(c['body'])}"
            for c in comments
        )
        return (
            f"Issue: {data['key']} ({f['issuetype']['name']})\n"
            f"Summary:  {f['summary']}\n"
            f"Status:   {f['status']['name']}\n"
            f"Assignee: {(f.get('assignee') or {}).get('displayName', 'Unassigned')}\n"
            f"Priority: {(f.get('priority') or {}).get('name', 'None')}\n"
            f"Labels:   {', '.join(f.get('labels', [])) or 'None'}\n"
            f"Created:  {f.get('created', '')[:10]}\n"
            f"Updated:  {f.get('updated', '')[:10]}\n"
            f"Description:\n  {_extract_text(f.get('description')) or '(none)'}\n"
            f"Recent Comments:\n{comment_lines or '  (none)'}"
        )

    # ── AUTO-APPROVED write tools ──────────────────────────────────────────────

    @mcp.tool()
    async def jira_add_comment(issue_key: str, comment: str, ctx: Context = None) -> str:
        """Add a plain-text comment to a Jira issue.

        Args:
            issue_key: Jira issue key, e.g. ``ENG-123``.
            comment: Comment body (plain text).

        Returns:
            Confirmation with the new comment ID.
        """
        app = ctx.request_context.lifespan_context
        result = await app.jira.post(
            f"/rest/api/3/issue/{issue_key}/comment",
            body={"body": _text_to_adf(comment)},
        )
        return f"Comment added to {issue_key} (id={result.get('id', '?')})."

    @mcp.tool()
    async def jira_add_label(issue_key: str, label: str, ctx: Context = None) -> str:
        """Add a label to a Jira issue without removing existing labels.

        Args:
            issue_key: Jira issue key, e.g. ``ENG-123``.
            label: Label string to add (no spaces).

        Returns:
            Confirmation listing all labels now on the issue.
        """
        app = ctx.request_context.lifespan_context
        data = await app.jira.get(
            f"/rest/api/3/issue/{issue_key}", params={"fields": "labels"}
        )
        existing: list[str] = data["fields"].get("labels", [])
        if label in existing:
            return f"Label '{label}' already present on {issue_key}."
        updated = existing + [label]
        await app.jira.put(
            f"/rest/api/3/issue/{issue_key}",
            body={"fields": {"labels": updated}},
        )
        return f"Label '{label}' added to {issue_key}. Labels: {', '.join(updated)}"

    # ── MEDIUM-RISK write tools (⚠️ WRITE) ────────────────────────────────────

    @mcp.tool()
    async def jira_create_issue(
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str | None = None,
        assignee_account_id: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
        ctx: Context = None,
    ) -> str:
        """⚠️ WRITE: Create a new Jira issue. Confirm project key and summary before calling.

        Args:
            project_key: Jira project key, e.g. ``ENG``.
            summary: Issue title / summary.
            issue_type: Issue type name (default ``Task``). Common values: Bug, Story, Task, Epic.
            description: Optional plain-text description.
            assignee_account_id: Atlassian account ID of the assignee (optional).
            priority: Priority name, e.g. ``High``, ``Medium``, ``Low`` (optional).
            labels: List of label strings (optional).

        Returns:
            New issue key and URL.
        """
        app = ctx.request_context.lifespan_context
        fields: dict = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = _text_to_adf(description)
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority:
            fields["priority"] = {"name": priority}
        if labels:
            fields["labels"] = labels

        result = await app.jira.post("/rest/api/3/issue", body={"fields": fields})
        key = result["key"]
        # Derive browse URL from the configured Jira base URL
        base = app.jira._base_url
        return f"Created {key}: {base}/browse/{key}"

    @mcp.tool()
    async def jira_update_issue(
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        assignee_account_id: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
        ctx: Context = None,
    ) -> str:
        """⚠️ WRITE: Update fields on an existing Jira issue. Only provided fields are changed.

        Args:
            issue_key: Jira issue key, e.g. ``ENG-123``.
            summary: New summary (optional).
            description: New plain-text description (optional).
            assignee_account_id: Atlassian account ID of the new assignee (optional).
            priority: New priority name (optional).
            labels: Replacement label list — replaces all existing labels (optional).

        Returns:
            Confirmation of the update.
        """
        app = ctx.request_context.lifespan_context
        fields: dict = {}
        if summary is not None:
            fields["summary"] = summary
        if description is not None:
            fields["description"] = _text_to_adf(description)
        if assignee_account_id is not None:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority is not None:
            fields["priority"] = {"name": priority}
        if labels is not None:
            fields["labels"] = labels

        if not fields:
            return "No fields provided — nothing to update."

        await app.jira.put(f"/rest/api/3/issue/{issue_key}", body={"fields": fields})
        updated = ", ".join(fields.keys())
        return f"Updated {issue_key}: {updated}."

    @mcp.tool()
    async def jira_link_issues(
        inward_issue_key: str,
        outward_issue_key: str,
        link_type: str = "blocks",
        ctx: Context = None,
    ) -> str:
        """⚠️ WRITE: Create a link between two Jira issues.

        Args:
            inward_issue_key: The issue that is the *source* of the link (e.g. ``ENG-10``).
            outward_issue_key: The issue that is the *target* of the link (e.g. ``ENG-20``).
            link_type: Link type name (default ``blocks``).
                       Common values: blocks, clones, duplicates, relates to.

        Returns:
            Confirmation of the created link.
        """
        app = ctx.request_context.lifespan_context
        await app.jira.post(
            "/rest/api/3/issueLink",
            body={
                "type": {"name": link_type},
                "inwardIssue": {"key": inward_issue_key},
                "outwardIssue": {"key": outward_issue_key},
            },
        )
        return f"Linked {inward_issue_key} → {outward_issue_key} ({link_type})."

    # ── HIGH-RISK tools (🔴 DESTRUCTIVE) ──────────────────────────────────────

    @mcp.tool()
    async def jira_transition_issue(
        issue_key: str, transition_name: str, ctx: Context = None
    ) -> str:
        """🔴 DESTRUCTIVE: Move a Jira issue to a new workflow status.

        This changes the issue state and may trigger automations or notifications.
        Always get explicit user confirmation (including the issue key and target
        status) before calling this tool.

        Args:
            issue_key: Jira issue key, e.g. ``ENG-123``.
            transition_name: Target status name (case-insensitive), e.g. ``In Progress``,
                             ``Done``, ``In Review``.

        Returns:
            Confirmation with old and new status, or a list of available transitions
            if the requested name was not found.
        """
        app = ctx.request_context.lifespan_context

        # Fetch current status + available transitions
        issue_data = await app.jira.get(
            f"/rest/api/3/issue/{issue_key}", params={"fields": "status"}
        )
        old_status = issue_data["fields"]["status"]["name"]

        transitions_data = await app.jira.get(
            f"/rest/api/3/issue/{issue_key}/transitions"
        )
        transitions: list[dict] = transitions_data.get("transitions", [])

        match = next(
            (t for t in transitions if t["name"].lower() == transition_name.lower()),
            None,
        )
        if not match:
            available = ", ".join(t["name"] for t in transitions)
            return (
                f"Transition '{transition_name}' not found for {issue_key}.\n"
                f"Available transitions: {available}"
            )

        await app.jira.post(
            f"/rest/api/3/issue/{issue_key}/transitions",
            body={"transition": {"id": match["id"]}},
        )
        return f"Transitioned {issue_key}: '{old_status}' → '{match['name']}'."
