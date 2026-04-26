"""Tests for confluence_tools.py"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from jira_confluence_mcp.confluence_tools import _strip_html, _text_to_storage


# ── Unit tests for helpers ────────────────────────────────────────────────────

def test_strip_html_removes_tags():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_decodes_entities():
    assert "&amp;" not in _strip_html("&amp;")
    assert "&" in _strip_html("&amp;")


def test_text_to_storage_wraps_paragraphs():
    result = _text_to_storage("line one\nline two")
    assert "<p>line one</p>" in result
    assert "<p>line two</p>" in result


# ── Tool behaviour tests ──────────────────────────────────────────────────────

def _make_ctx(confluence_mock):
    ctx = MagicMock()
    ctx.request_context.lifespan_context.confluence = confluence_mock
    return ctx


def _register():
    from jira_confluence_mcp import confluence_tools
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    confluence_tools.register(mcp)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


@pytest.mark.asyncio
async def test_confluence_search_returns_results():
    confluence = AsyncMock()
    confluence._base_url = "https://test.atlassian.net"
    confluence.get.return_value = {
        "totalSize": 1,
        "results": [
            {
                "id": "123",
                "title": "Onboarding Guide",
                "space": {"key": "ENG"},
                "version": {"when": "2024-01-15T10:00:00Z"},
                "_links": {"webui": "/spaces/ENG/pages/123"},
            }
        ],
    }

    tools = _register()
    result = await tools["confluence_search"](cql="title ~ onboarding", ctx=_make_ctx(confluence))
    assert "Onboarding Guide" in result
    assert "ENG" in result


@pytest.mark.asyncio
async def test_confluence_search_empty():
    confluence = AsyncMock()
    confluence.get.return_value = {"totalSize": 0, "results": []}
    tools = _register()
    result = await tools["confluence_search"](cql="title ~ nothing", ctx=_make_ctx(confluence))
    assert "No Confluence pages found" in result


@pytest.mark.asyncio
async def test_confluence_get_page_strips_html():
    confluence = AsyncMock()
    confluence._base_url = "https://test.atlassian.net"
    confluence.get.return_value = {
        "id": "456",
        "title": "My Page",
        "spaceId": "789",
        "version": {"number": 3},
        "body": {"storage": {"value": "<p>Hello <b>world</b></p>"}},
        "_links": {"webui": "/spaces/ENG/pages/456"},
    }

    tools = _register()
    result = await tools["confluence_get_page"](page_id="456", ctx=_make_ctx(confluence))
    assert "My Page" in result
    assert "Hello" in result
    assert "<p>" not in result  # HTML stripped


@pytest.mark.asyncio
async def test_confluence_update_page_increments_version():
    confluence = AsyncMock()
    confluence._base_url = "https://test.atlassian.net"
    confluence.get.return_value = {
        "version": {"number": 5},
        "_links": {"webui": "/spaces/ENG/pages/456"},
    }
    confluence.put.return_value = {
        "id": "456",
        "_links": {"webui": "/spaces/ENG/pages/456"},
    }

    tools = _register()
    await tools["confluence_update_page"](
        page_id="456", title="Updated Title", body="New content", ctx=_make_ctx(confluence)
    )

    put_call = confluence.put.call_args
    version_sent = put_call[1]["body"]["version"]["number"]
    assert version_sent == 6  # 5 + 1


@pytest.mark.asyncio
async def test_confluence_create_page_returns_id_and_url():
    confluence = AsyncMock()
    confluence._base_url = "https://test.atlassian.net"
    confluence.post.return_value = {
        "id": "999",
        "_links": {"webui": "/spaces/ENG/pages/999"},
    }

    tools = _register()
    result = await tools["confluence_create_page"](
        space_id="42", title="New Page", body="Content here", ctx=_make_ctx(confluence)
    )
    assert "999" in result
    assert "New Page" in result
