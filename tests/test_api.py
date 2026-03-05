"""Tests for FastAPI endpoints (src/api/endpoints.py)"""

import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api.endpoints import app

client = TestClient(app)


def _mock_asyncio_run(coro):
    coro.close()  # prevent "coroutine was never awaited" warnings
    return "Page text"


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_research_streams_events():
    search_result = [{"url": "https://example.com", "title": "Example", "content": "Test"}]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="LLM output text.")

    with (
        patch("src.graph.nodes.perform_search", return_value=search_result),
        patch("src.graph.nodes.asyncio.run", side_effect=_mock_asyncio_run),
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.graph.nodes.VectorStoreManager"),
    ):
        response = client.post(
            "/research",
            json={"query": "What is LangGraph?", "use_vector_store": False},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    # Parse SSE lines
    events = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    node_names = [e["node"] for e in events]
    assert "__end__" in node_names


def test_research_bad_request_returns_422():
    response = client.post("/research", json={})  # missing 'query'
    assert response.status_code == 422
