"""Tests for jira_tools.py"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from jira_confluence_mcp.jira_tools import _extract_text, _text_to_adf


# ── Unit tests for helpers ────────────────────────────────────────────────────

def test_extract_text_plain():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}
        ],
    }
    assert "Hello world" in _extract_text(adf)


def test_extract_text_none():
    assert _extract_text(None) == ""


def test_text_to_adf_structure():
    doc = _text_to_adf("line one\nline two")
    assert doc["type"] == "doc"
    assert doc["version"] == 1
    assert len(doc["content"]) == 2
    assert doc["content"][0]["content"][0]["text"] == "line one"


# ── Tool behaviour tests (mock AtlassianClient) ───────────────────────────────

def _make_ctx(jira_mock):
    """Build a minimal fake MCP Context with a mocked jira client."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context.jira = jira_mock
    return ctx


@pytest.mark.asyncio
async def test_jira_search_returns_formatted_results():
    jira = AsyncMock()
    jira.get.return_value = {
        "total": 1,
        "issues": [
            {
                "key": "ENG-1",
                "fields": {
                    "summary": "Fix login bug",
                    "status": {"name": "In Progress"},
                    "assignee": {"displayName": "Alice"},
                    "priority": {"name": "High"},
                    "labels": [],
                },
            }
        ],
    }

    # Import and call the registered tool function directly
    from jira_confluence_mcp import jira_tools
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    jira_tools.register(mcp)

    # Grab the tool function by name from the registered tools
    tool_fn = next(t.fn for t in mcp._tool_manager.list_tools() if t.name == "jira_search")
    result = await tool_fn(jql="project = ENG", ctx=_make_ctx(jira))

    assert "ENG-1" in result
    assert "Fix login bug" in result
    assert "In Progress" in result


@pytest.mark.asyncio
async def test_jira_search_empty():
    jira = AsyncMock()
    jira.get.return_value = {"total": 0, "issues": []}

    from jira_confluence_mcp import jira_tools
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    jira_tools.register(mcp)
    tool_fn = next(t.fn for t in mcp._tool_manager.list_tools() if t.name == "jira_search")
    result = await tool_fn(jql="project = EMPTY", ctx=_make_ctx(jira))
    assert "No issues found" in result


@pytest.mark.asyncio
async def test_jira_add_label_preserves_existing():
    jira = AsyncMock()
    jira.get.return_value = {"fields": {"labels": ["existing"]}}
    jira.put.return_value = {}

    from jira_confluence_mcp import jira_tools
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    jira_tools.register(mcp)
    tool_fn = next(t.fn for t in mcp._tool_manager.list_tools() if t.name == "jira_add_label")
    result = await tool_fn(issue_key="ENG-1", label="new-label", ctx=_make_ctx(jira))

    # Verify PUT was called with both labels
    put_call = jira.put.call_args
    labels_sent = put_call[1]["body"]["fields"]["labels"]
    assert "existing" in labels_sent
    assert "new-label" in labels_sent
    assert "new-label" in result


@pytest.mark.asyncio
async def test_jira_transition_issue_not_found_returns_available():
    jira = AsyncMock()
    jira.get.side_effect = [
        {"fields": {"status": {"name": "To Do"}}},
        {"transitions": [{"id": "11", "name": "In Progress"}, {"id": "31", "name": "Done"}]},
    ]

    from jira_confluence_mcp import jira_tools
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    jira_tools.register(mcp)
    tool_fn = next(t.fn for t in mcp._tool_manager.list_tools() if t.name == "jira_transition_issue")
    result = await tool_fn(issue_key="ENG-1", transition_name="Nonexistent", ctx=_make_ctx(jira))

    assert "not found" in result.lower()
    assert "In Progress" in result
    assert "Done" in result


@pytest.mark.asyncio
async def test_jira_create_issue_returns_key_and_url():
    jira = AsyncMock()
    jira.post.return_value = {"key": "ENG-99"}
    jira._base_url = "https://test.atlassian.net"

    from jira_confluence_mcp import jira_tools
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    jira_tools.register(mcp)
    tool_fn = next(t.fn for t in mcp._tool_manager.list_tools() if t.name == "jira_create_issue")
    result = await tool_fn(project_key="ENG", summary="New task", ctx=_make_ctx(jira))

    assert "ENG-99" in result
    assert "browse/ENG-99" in result
