from unittest.mock import AsyncMock, patch

from src.sessions import ConversationTurn, SessionRun, append_run, append_turn, create_session, get_session


async def test_sessions_module_delegates_create_to_store():
    mock_store = AsyncMock()
    mock_store.create_session.return_value = "session-object"
    with patch("src.sessions._get_store", return_value=mock_store):
        created = await create_session("user-1")
    assert created == "session-object"
    mock_store.create_session.assert_awaited_once_with(user_id="user-1")


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
