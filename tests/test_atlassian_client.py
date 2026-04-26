"""Tests for atlassian_client.py"""
import base64
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from jira_confluence_mcp.atlassian_client import AtlassianClient, AtlassianAPIError


def make_client():
    return AtlassianClient("https://test.atlassian.net", "user@test.com", "mytoken")


def test_auth_header_is_basic_base64():
    client = make_client()
    expected = "Basic " + base64.b64encode(b"user@test.com:mytoken").decode()
    assert client._headers["Authorization"] == expected


def test_base_url_strips_trailing_slash():
    client = AtlassianClient("https://test.atlassian.net/", "u", "t")
    assert client._base_url == "https://test.atlassian.net"


@pytest.mark.asyncio
async def test_get_returns_json():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "ENG-1"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        client = make_client()
        result = await client.get("/rest/api/3/issue/ENG-1")
    assert result["key"] == "ENG-1"


@pytest.mark.asyncio
async def test_get_raises_atlassian_api_error_on_404():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"
    mock_response.reason_phrase = "Not Found"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )
        client = make_client()
        with pytest.raises(AtlassianAPIError) as exc_info:
            await client.get("/rest/api/3/issue/MISSING-1")
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_raises_on_401():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.reason_phrase = "Unauthorized"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )
        client = make_client()
        with pytest.raises(AtlassianAPIError) as exc_info:
            await client.get("/rest/api/3/issue/ENG-1")
    assert exc_info.value.status_code == 401
    assert "authentication" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_post_returns_empty_dict_on_no_content():
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.content = b""
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        client = make_client()
        result = await client.post("/rest/api/3/issue/ENG-1/transitions", body={"transition": {"id": "31"}})
    assert result == {}
