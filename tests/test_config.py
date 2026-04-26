"""Tests for config.py"""
import pytest
from unittest.mock import patch


def _env(**kwargs):
    """Return a minimal valid env dict, overridable via kwargs."""
    base = {
        "JIRA_URL": "https://test.atlassian.net",
        "JIRA_USERNAME": "user@test.com",
        "JIRA_API_TOKEN": "token123",
    }
    base.update(kwargs)
    return base


def test_loads_from_env():
    with patch.dict("os.environ", _env(), clear=True):
        from jira_confluence_mcp.config import Config
        c = Config.from_env()
    assert c.jira_url == "https://test.atlassian.net"
    assert c.jira_username == "user@test.com"
    assert c.jira_api_token == "token123"


def test_confluence_defaults_to_jira():
    with patch.dict("os.environ", _env(), clear=True):
        from jira_confluence_mcp.config import Config
        c = Config.from_env()
    assert c.confluence_url == "https://test.atlassian.net/wiki"
    assert c.confluence_username == "user@test.com"
    assert c.confluence_api_token == "token123"


def test_confluence_explicit_override():
    env = _env(
        CONFLUENCE_URL="https://other.atlassian.net/wiki",
        CONFLUENCE_USERNAME="other@test.com",
        CONFLUENCE_API_TOKEN="other_token",
    )
    with patch.dict("os.environ", env, clear=True):
        from jira_confluence_mcp.config import Config
        c = Config.from_env()
    assert c.confluence_url == "https://other.atlassian.net/wiki"
    assert c.confluence_username == "other@test.com"


def test_raises_on_missing_required():
    with patch.dict("os.environ", {}, clear=True):
        from jira_confluence_mcp.config import Config
        with pytest.raises(ValueError, match="JIRA_URL"):
            Config.from_env()


def test_repr_masks_token():
    with patch.dict("os.environ", _env(), clear=True):
        from jira_confluence_mcp.config import Config
        r = repr(Config.from_env())
    assert "token123" not in r
    assert "***" in r
