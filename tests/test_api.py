"""Tests for FastAPI endpoints (src/api/endpoints.py)"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.api.endpoints import app
from src.auth import AuthenticatedUser, get_authenticated_user
from src.sessions import Session, SessionRun

client = TestClient(app)


def _mock_asyncio_run(coro):
    coro.close()  # prevent "coroutine was never awaited" warnings
    return "Page text"


def _auth_override() -> AuthenticatedUser:
    return AuthenticatedUser(user_id="test-user", email="test@example.com")


app.dependency_overrides[get_authenticated_user] = _auth_override


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
    mock_session = Session(
        session_id="session-1",
        title="LangGraph basics",
        created_at="2026-01-01T00:00:00+00:00",
    )
    with patch("src.api.endpoints.create_session", new=AsyncMock(return_value=mock_session)):
        response = client.post("/sessions", json={"query": "What is LangGraph?"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-1"
    assert data["title"] == "LangGraph basics"
    assert data["created_at"] == "2026-01-01T00:00:00+00:00"


def test_get_session_returns_session_state():
    mock_session = Session(session_id="session-1", runs=[], conversation=[], created_at="2026")
    with patch("src.api.endpoints.get_session", new=AsyncMock(return_value=mock_session)):
        get_resp = client.get("/sessions/session-1")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["session_id"] == "session-1"
        assert data["runs"] == []
        assert data["conversation"] == []


def test_list_sessions_returns_summaries():
    with patch(
        "src.api.endpoints.list_sessions",
        new=AsyncMock(
            return_value=[
                {
                    "session_id": "session-1",
                    "title": "LangGraph basics",
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "session_id": "session-2",
                    "title": "Agent architecture",
                    "created_at": "2026-01-02T00:00:00+00:00",
                },
            ]
        ),
    ):
        response = client.get("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 2
    assert data["sessions"][0]["session_id"] == "session-1"


def test_get_session_returns_404_for_unknown_id():
    with patch("src.api.endpoints.get_session", new=AsyncMock(return_value=None)):
        response = client.get("/sessions/does-not-exist")
        assert response.status_code == 404


def test_followup_returns_400_when_no_run_exists():
    mock_session = Session(session_id="session-1", runs=[], conversation=[], created_at="2026")
    with patch("src.api.endpoints.get_session", new=AsyncMock(return_value=mock_session)):
        followup_resp = client.post(
            "/sessions/session-1/followup",
            json={"question": "What did you find?"},
        )
        assert followup_resp.status_code == 400


def test_followup_returns_404_for_unknown_session():
    with patch("src.api.endpoints.get_session", new=AsyncMock(return_value=None)):
        response = client.post(
            "/sessions/no-such-session/followup",
            json={"question": "anything"},
        )
        assert response.status_code == 404


def test_followup_returns_404_for_unknown_run_id():
    mock_session = Session(session_id="session-1", runs=[], conversation=[], created_at="2026")
    with patch("src.api.endpoints.get_session", new=AsyncMock(return_value=mock_session)):
        response = client.post(
            "/sessions/session-1/followup",
            json={"question": "anything", "run_id": "nonexistent-run"},
        )
        assert response.status_code == 404


def test_session_research_streams_events_and_records_run():
    search_result = [{"url": "https://example.com", "title": "Example", "content": "Test"}]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="LLM output text.")

    mock_session = Session(
        session_id="session-1",
        runs=[SessionRun(run_id="old", query="q", source_urls=[], report="", created_at="2026")],
        conversation=[],
        created_at="2026",
    )

    with (
        patch("src.graph.nodes.perform_search", return_value=search_result),
        patch("src.graph.nodes.asyncio.run", side_effect=_mock_asyncio_run),
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.graph.nodes.VectorStoreManager"),
        patch("src.api.endpoints.VectorStoreManager"),
        patch("src.api.endpoints.get_session", new=AsyncMock(return_value=mock_session)),
        patch("src.api.endpoints.append_run", new=AsyncMock(return_value=None)),
    ):
        response = client.post(
            "/sessions/session-1/research",
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

    assert response.headers.get("X-Run-Id")


def test_session_endpoints_require_auth():
    app.dependency_overrides.pop(get_authenticated_user, None)
    try:
        create_resp = client.post("/sessions", json={})
        assert create_resp.status_code == 401
    finally:
        app.dependency_overrides[get_authenticated_user] = _auth_override


def test_startup_validation_does_not_fail_without_supabase_configuration():
    with (
        patch("src.api.endpoints.settings.supabase_url", ""),
        patch("src.api.endpoints.settings.supabase_service_role_key", ""),
        patch("src.api.endpoints.ensure_store_initialized") as mock_init,
    ):
        asyncio.run(app.router.on_startup[0]())
        mock_init.assert_not_called()


# ---------------------------------------------------------------------------
# Follow-up suggestion tests
# ---------------------------------------------------------------------------

def test_generate_suggestions_returns_list():
    """_generate_suggestions parses numbered lines into a list of strings."""
    from src.api.endpoints import _generate_suggestions

    mock_result = MagicMock()
    mock_result.content = "1. What are the limitations?\n2. How does it compare to X?\n3. What are real-world use cases?"

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_result)

    with patch("src.api.endpoints.get_llm", return_value=mock_llm):
        suggestions = asyncio.run(
            _generate_suggestions("What is LangGraph?", "LangGraph is a library...", "topics: graphs, agents")
        )

    assert isinstance(suggestions, list)
    assert len(suggestions) == 3
    assert suggestions[0] == "What are the limitations?"
    assert suggestions[1] == "How does it compare to X?"
    assert suggestions[2] == "What are real-world use cases?"


def test_generate_suggestions_returns_empty_on_error():
    """_generate_suggestions returns [] when the LLM raises an exception."""
    from src.api.endpoints import _generate_suggestions

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))

    with patch("src.api.endpoints.get_llm", return_value=mock_llm):
        suggestions = asyncio.run(
            _generate_suggestions("What is LangGraph?", "Some answer", "context")
        )

    assert suggestions == []


def test_followup_stream_includes_suggestions_event():
    """The followup SSE stream emits a 'suggestions' event after citations."""
    mock_chunk = MagicMock()
    mock_chunk.content = "Here is the answer."

    mock_llm = MagicMock()
    mock_llm.astream = MagicMock(return_value=_async_iter([mock_chunk]))

    mock_suggestions_llm = AsyncMock()
    mock_suggestions_result = MagicMock()
    mock_suggestions_result.content = "1. Question one?\n2. Question two?\n3. Question three?"
    mock_suggestions_llm.ainvoke = AsyncMock(return_value=mock_suggestions_result)

    mock_session = Session(
        session_id="session-1",
        runs=[SessionRun(run_id="run-1", query="q", source_urls=[], report="", created_at="2026")],
        conversation=[],
        created_at="2026",
    )

    def get_llm_side_effect(temperature=0.2):
        if temperature == 0.7:
            return mock_suggestions_llm
        return mock_llm

    with (
        patch("src.api.endpoints.get_session", new=AsyncMock(return_value=mock_session)),
        patch("src.api.endpoints.VectorStoreManager"),
        patch("src.api.endpoints.append_turn", new=AsyncMock(return_value=None)),
        patch("src.api.endpoints.get_llm", side_effect=get_llm_side_effect),
    ):
        response = client.post(
            "/sessions/session-1/followup",
            json={"question": "What did you find?", "run_id": "run-1"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    event_types = [e["type"] for e in events]
    assert "suggestions" in event_types

    suggestions_event = next(e for e in events if e["type"] == "suggestions")
    assert isinstance(suggestions_event["suggestions"], list)
    assert len(suggestions_event["suggestions"]) > 0

    # suggestions must appear before done
    suggestions_idx = event_types.index("suggestions")
    done_idx = event_types.index("done")
    assert suggestions_idx < done_idx


async def _async_iter_impl(items):
    for item in items:
        yield item


def _async_iter(items):
    return _async_iter_impl(items)
