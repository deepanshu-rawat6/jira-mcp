"""FastMCP server entry point for the Jira & Confluence MCP server.

Starts an MCP server over stdio (default) that exposes Jira and Confluence
tools to any MCP-compatible client (e.g. kiro-cli).

Usage:
    uv run python -m jira_confluence_mcp
    # or via the installed script:
    jira-confluence-mcp
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from .atlassian_client import AtlassianClient
from .config import Config
from . import confluence_tools, jira_tools


@dataclass
class AppContext:
    """Shared clients injected into every tool call via the lifespan context."""

    jira: AtlassianClient
    confluence: AtlassianClient


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Initialise Atlassian clients on startup; clean up on shutdown."""
    config = Config.from_env()
    yield AppContext(
        jira=AtlassianClient(config.jira_url, config.jira_username, config.jira_api_token),
        confluence=AtlassianClient(
            config.confluence_url, config.confluence_username, config.confluence_api_token
        ),
    )


mcp = FastMCP("Atlassian MCP", lifespan=_lifespan)

# Register all tools
jira_tools.register(mcp)
confluence_tools.register(mcp)


def main() -> None:
    """Run the MCP server (stdio transport by default)."""
    mcp.run()


if __name__ == "__main__":
    main()
