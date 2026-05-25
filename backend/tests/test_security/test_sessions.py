import pytest
import uuid

from app.auth.sessions import SessionManager


class TestSessionManager:
    @pytest.fixture(autouse=True)
    def check_redis(self):
        try:
            import redis.asyncio as redis_lib
            r = redis_lib.from_url("redis://localhost:6379/0", decode_responses=True)
            # synchronous check - just try to create connection
            import asyncio
            asyncio.get_event_loop().run_until_complete(r.ping())
        except Exception as exc:
            pytest.skip(f"Redis not available: {exc}")

    @pytest.mark.asyncio
    async def test_create_and_get_session(self):
        user_id = f"user-{uuid.uuid4()}"
        session_id = await SessionManager.create_session(
            user_id=user_id,
            device_fingerprint="fp-abc",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )
        assert session_id is not None
        assert len(session_id) == 36

        session = await SessionManager.get_session(session_id)
        assert session is not None
        assert session["user_id"] == user_id
        assert session["ip_address"] == "192.168.1.1"

        await SessionManager.destroy_session(session_id)

    @pytest.mark.asyncio
    async def test_update_activity(self):
        user_id = f"user-{uuid.uuid4()}"
        session_id = await SessionManager.create_session(user_id=user_id)
        success = await SessionManager.update_activity(session_id)
        assert success is True

        session = await SessionManager.get_session(session_id)
        assert "last_activity_at" in session
        await SessionManager.destroy_session(session_id)

    @pytest.mark.asyncio
    async def test_destroy_session(self):
        user_id = f"user-{uuid.uuid4()}"
        session_id = await SessionManager.create_session(user_id=user_id)
        await SessionManager.destroy_session(session_id)
        session = await SessionManager.get_session(session_id)
        assert session is None

    @pytest.mark.asyncio
    async def test_is_session_valid(self):
        user_id = f"user-{uuid.uuid4()}"
        session_id = await SessionManager.create_session(user_id=user_id)
        assert await SessionManager.is_session_valid(session_id) is True
        await SessionManager.destroy_session(session_id)
        assert await SessionManager.is_session_valid(session_id) is False

    @pytest.mark.asyncio
    async def test_list_user_sessions(self):
        user_id = f"user-{uuid.uuid4()}"
        sid1 = await SessionManager.create_session(user_id=user_id)
        sid2 = await SessionManager.create_session(user_id=user_id)

        sessions = await SessionManager.list_user_sessions(user_id)
        assert len(sessions) == 2
        session_ids = {s["session_id"] for s in sessions}
        assert sid1 in session_ids
        assert sid2 in session_ids

        await SessionManager.destroy_all_user_sessions(user_id)
        sessions = await SessionManager.list_user_sessions(user_id)
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_destroy_all_except_one(self):
        user_id = f"user-{uuid.uuid4()}"
        sid1 = await SessionManager.create_session(user_id=user_id)
        sid2 = await SessionManager.create_session(user_id=user_id)
        sid3 = await SessionManager.create_session(user_id=user_id)

        count = await SessionManager.destroy_all_user_sessions(user_id, except_session=sid2)
        assert count == 2

        assert await SessionManager.is_session_valid(sid1) is False
        assert await SessionManager.is_session_valid(sid2) is True
        assert await SessionManager.is_session_valid(sid3) is False

        await SessionManager.destroy_session(sid2)
