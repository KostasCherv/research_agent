from unittest.mock import AsyncMock, MagicMock, patch

from src.db.supabase_store import SupabaseSessionStore
from src.sessions import ConversationTurn, SessionRun, append_run, append_turn, create_session, get_session


async def test_sessions_module_delegates_create_to_store():
    mock_store = AsyncMock()
    mock_store.create_session.return_value = "session-object"
    with patch("src.sessions._get_store", return_value=mock_store):
        created = await create_session("user-1")
    assert created == "session-object"
    mock_store.create_session.assert_awaited_once_with(user_id="user-1", title="New session")


async def test_sessions_module_delegates_get_to_store():
    mock_store = AsyncMock()
    mock_store.get_session.return_value = None
    with patch("src.sessions._get_store", return_value=mock_store):
        session = await get_session("session-1", "user-1")
    assert session is None
    mock_store.get_session.assert_awaited_once_with(session_id="session-1", user_id="user-1")


async def test_sessions_module_delegates_append_operations():
    mock_store = AsyncMock()
    run = SessionRun(run_id="r1", query="q")
    turn = ConversationTurn(role="user", content="c")
    with patch("src.sessions._get_store", return_value=mock_store):
        await append_run("user-1", "session-1", run)
        await append_turn("user-1", "session-1", turn)
    mock_store.append_run.assert_awaited_once_with(user_id="user-1", session_id="session-1", run=run)
    mock_store.append_turn.assert_awaited_once_with(user_id="user-1", session_id="session-1", turn=turn)


async def test_store_lists_rag_chat_sessions_with_batched_latest_messages():
    store = object.__new__(SupabaseSessionStore)
    sessions_response = MagicMock()
    sessions_response.json.return_value = [
        {
            "id": "chat-1",
            "owner_id": "user-1",
            "workspace_id": "user-1",
            "agent_id": "agent-1",
            "created_at": "2026-04-23T09:00:00+00:00",
        },
        {
            "id": "chat-2",
            "owner_id": "user-1",
            "workspace_id": "user-1",
            "agent_id": "agent-1",
            "created_at": "2026-04-23T10:00:00+00:00",
        },
    ]
    messages_response = MagicMock()
    messages_response.json.return_value = [
        {
            "session_id": "chat-2",
            "content": "Most recent chat",
            "created_at": "2026-04-23T10:05:00+00:00",
        },
        {
            "session_id": "chat-1",
            "content": "Earlier chat",
            "created_at": "2026-04-23T09:05:00+00:00",
        },
    ]
    store._request = AsyncMock(side_effect=[sessions_response, messages_response])  # type: ignore[method-assign]

    summaries = await store.list_rag_chat_sessions(agent_id="agent-1", owner_id="user-1")

    assert store._request.await_count == 2
    messages_call = store._request.await_args_list[1]
    assert messages_call.args == ("GET", "rag_chat_messages")
    assert messages_call.kwargs["params"]["session_id"] == "in.(chat-1,chat-2)"
    assert summaries[0]["session_id"] == "chat-2"
    assert summaries[0]["title"] == "New chat"
    assert summaries[0]["last_message_preview"] == "Most recent chat"
