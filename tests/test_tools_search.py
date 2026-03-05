"""Tests for src/tools/search.py"""

from unittest.mock import patch, MagicMock, call
import pytest

from src.errors import SearchError


def _make_tavily_response(n: int = 2) -> dict:
    return {
        "results": [
            {"url": f"https://example.com/{i}", "title": f"Title {i}", "content": f"Content {i}"}
            for i in range(n)
        ]
    }


def test_perform_search_returns_results():
    mock_client = MagicMock()
    mock_client.search.return_value = _make_tavily_response(3)

    with (
        patch("src.tools.search.settings") as mock_settings,
        # Patch at the tavily package level so the real network call is skipped
        patch("tavily.TavilyClient", return_value=mock_client),
    ):
        mock_settings.tavily_api_key = "tvly-test"
        mock_settings.max_search_results = 5

        from src.tools.search import perform_search

        results = perform_search("LangGraph tutorial")

    assert len(results) == 3
    assert results[0]["url"] == "https://example.com/0"
    assert "title" in results[0]
    assert "content" in results[0]


def test_perform_search_raises_without_api_key():
    with patch("src.tools.search.settings") as mock_settings:
        mock_settings.tavily_api_key = ""
        mock_settings.max_search_results = 5

        from src.tools.search import perform_search

        with pytest.raises(SearchError):
            perform_search("anything")


def test_perform_search_retries_on_failure():
    mock_client = MagicMock()
    mock_client.search.side_effect = [
        RuntimeError("network error"),
        RuntimeError("network error"),
        _make_tavily_response(1),
    ]

    with (
        patch("src.tools.search.settings") as mock_settings,
        patch("tavily.TavilyClient", return_value=mock_client),
        patch("src.tools.search.time.sleep"),  # suppress actual sleep
    ):
        mock_settings.tavily_api_key = "tvly-test"
        mock_settings.max_search_results = 5

        from src.tools.search import perform_search

        results = perform_search("LangGraph")

    assert len(results) == 1
    assert mock_client.search.call_count == 3


def test_perform_search_raises_after_all_retries():
    mock_client = MagicMock()
    mock_client.search.side_effect = RuntimeError("always fails")

    with (
        patch("src.tools.search.settings") as mock_settings,
        patch("tavily.TavilyClient", return_value=mock_client),
        patch("src.tools.search.time.sleep"),
    ):
        mock_settings.tavily_api_key = "tvly-test"
        mock_settings.max_search_results = 5

        from src.tools.search import perform_search

        with pytest.raises(SearchError):
            perform_search("fail query")
