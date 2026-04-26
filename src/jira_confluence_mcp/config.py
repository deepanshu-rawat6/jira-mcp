"""Configuration loader for Jira & Confluence MCP server.

Reads credentials from environment variables (or a .env file).
Confluence vars default to Jira values when not explicitly set,
since both products share the same Atlassian Cloud domain.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Holds all credentials needed to talk to Jira and Confluence."""

    jira_url: str
    jira_username: str
    jira_api_token: str
    confluence_url: str
    confluence_username: str
    confluence_api_token: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables.

        CONFLUENCE_* vars fall back to JIRA_* values when absent,
        because on Atlassian Cloud both products live under the same domain.

        Raises:
            ValueError: If any required variable is missing.
        """
        jira_url = os.getenv("JIRA_URL", "")
        jira_username = os.getenv("JIRA_USERNAME", "")
        jira_api_token = os.getenv("JIRA_API_TOKEN", "")

        values = {
            "jira_url": jira_url,
            "jira_username": jira_username,
            "jira_api_token": jira_api_token,
            "confluence_url": os.getenv("CONFLUENCE_URL", jira_url.rstrip("/") + "/wiki" if jira_url else ""),
            "confluence_username": os.getenv("CONFLUENCE_USERNAME", jira_username),
            "confluence_api_token": os.getenv("CONFLUENCE_API_TOKEN", jira_api_token),
        }

        missing = [k.upper() for k, v in values.items() if not v]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(**values)

    def __repr__(self) -> str:
        return (
            f"Config(jira_url={self.jira_url!r}, "
            f"jira_username={self.jira_username!r}, "
            f"jira_api_token=***, "
            f"confluence_url={self.confluence_url!r})"
        )
