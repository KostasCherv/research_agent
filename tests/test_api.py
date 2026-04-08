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


# ---------------------------------------------------------------------------
# Session endpoint tests
# ---------------------------------------------------------------------------

def test_create_session_returns_session_id():
    response = client.post("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "created_at" in data


def test_get_session_returns_session_state():
    create_resp = client.post("/sessions")
    session_id = create_resp.json()["session_id"]

    get_resp = client.get(f"/sessions/{session_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["session_id"] == session_id
    assert data["runs"] == []
    assert data["conversation"] == []


def test_get_session_returns_404_for_unknown_id():
    response = client.get("/sessions/does-not-exist")
    assert response.status_code == 404


def test_followup_returns_400_when_no_run_exists():
    create_resp = client.post("/sessions")
    session_id = create_resp.json()["session_id"]

    followup_resp = client.post(
        f"/sessions/{session_id}/followup",
        json={"question": "What did you find?"},
    )
    assert followup_resp.status_code == 400


def test_followup_returns_404_for_unknown_session():
    response = client.post(
        "/sessions/no-such-session/followup",
        json={"question": "anything"},
    )
    assert response.status_code == 404


def test_followup_returns_404_for_unknown_run_id():
    create_resp = client.post("/sessions")
    session_id = create_resp.json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/followup",
        json={"question": "anything", "run_id": "nonexistent-run"},
    )
    assert response.status_code == 404


def test_session_research_streams_events_and_records_run():
    search_result = [{"url": "https://example.com", "title": "Example", "content": "Test"}]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="LLM output text.")

    # Create session first
    create_resp = client.post("/sessions")
    session_id = create_resp.json()["session_id"]

    with (
        patch("src.graph.nodes.perform_search", return_value=search_result),
        patch("src.graph.nodes.asyncio.run", side_effect=_mock_asyncio_run),
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.graph.nodes.VectorStoreManager"),
        patch("src.api.endpoints.VectorStoreManager"),
    ):
        response = client.post(
            f"/sessions/{session_id}/research",
            json={"query": "What is LangGraph?", "use_vector_store": False},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers.get("X-Run-Id")

    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    node_names = [e["node"] for e in events]
    assert "__end__" in node_names

    # Session should now have one run recorded
    session_resp = client.get(f"/sessions/{session_id}")
    session_data = session_resp.json()
    assert len(session_data["runs"]) == 1
    assert session_data["runs"][0]["query"] == "What is LangGraph?"
