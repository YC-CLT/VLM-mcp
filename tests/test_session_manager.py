import pytest
from session_manager import SessionNotFoundError, SessionFullError, session_manager


@pytest.mark.asyncio
async def test_create_and_get_session():
    sid = await session_manager.create("llama-cpp")
    session = await session_manager.get(sid)
    assert session.id == sid
    assert session.backend == "llama-cpp"
    await session_manager.close(sid)


@pytest.mark.asyncio
async def test_close_session():
    sid = await session_manager.create("llama-cpp")
    await session_manager.close(sid)
    with pytest.raises(SessionNotFoundError):
        await session_manager.get(sid)


@pytest.mark.asyncio
async def test_list_sessions():
    sid = await session_manager.create("llama-cpp")
    sessions = await session_manager.list_sessions()
    assert any(s["id"] == sid for s in sessions)
    await session_manager.close(sid)