"""Tests for src/tools/fetcher.py"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.errors import FetchError


@pytest.mark.asyncio
async def test_fetch_url_content_returns_text():
    html = "<html><body><p>Hello World</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.fetcher.httpx.AsyncClient", return_value=mock_client):
        from src.tools.fetcher import fetch_url_content

        result = await fetch_url_content("https://example.com")

    assert "Hello World" in result


@pytest.mark.asyncio
async def test_fetch_url_content_raises_on_http_error():
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 404
    http_error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=http_error)

    with patch("src.tools.fetcher.httpx.AsyncClient", return_value=mock_client):
        from src.tools.fetcher import fetch_url_content

        with pytest.raises(FetchError, match="404"):
            await fetch_url_content("https://bad.example.com")


def test_clean_html_strips_tags():
    from src.tools.fetcher import clean_html

    html = "<html><head><style>body{}</style></head><body><p>Clean text</p></body></html>"
    result = clean_html(html)
    assert "Clean text" in result
    assert "<" not in result


def test_clean_html_truncates_long_content():
    from src.tools.fetcher import clean_html, _MAX_CHARS

    long_text = "word " * 10_000
    html = f"<body><p>{long_text}</p></body>"
    result = clean_html(html)
    assert len(result) <= _MAX_CHARS
