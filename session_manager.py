import asyncio
import time
import uuid
from dataclasses import dataclass, field

import config
from logger import get_logger

logger = get_logger()


@dataclass
class Session:
    id: str
    backend: str
    messages: list[dict] = field(default_factory=list)
    image_uris: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    msg_count: int = 0
    in_use: bool = False


class SessionNotFoundError(Exception):
    pass


class SessionFullError(Exception):
    pass


class SessionManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._sessions: dict[str, Session] = {}
        self._cleanup_task: asyncio.Task | None = None

    async def create(self, backend: str) -> str:
        async with self._lock:
            backend_sessions = [
                s for s in self._sessions.values() if s.backend == backend
            ]
            if len(backend_sessions) >= config.SESSION_MAX:
                evictable = sorted(
                    [s for s in backend_sessions if not s.in_use],
                    key=lambda s: s.last_active,
                )
                if evictable:
                    evicted = evictable[0]
                    del self._sessions[evicted.id]
                    logger.info(
                        "Session %s evicted (backend=%s full)", evicted.id, backend
                    )
                else:
                    raise SessionFullError(
                        f"Backend '{backend}' has {config.SESSION_MAX} active sessions"
                    )
            session = Session(id=str(uuid.uuid4()), backend=backend)
            self._sessions[session.id] = session
            logger.info("Session %s created (backend=%s)", session.id, backend)
            return session.id

    async def get(self, session_id: str) -> Session:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(f"Session {session_id} not found")
            session.last_active = time.time()
            return session

    async def close(self, session_id: str) -> None:
        async with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFoundError(f"Session {session_id} not found")
            del self._sessions[session_id]
            logger.info("Session %s closed", session_id)

    async def list_sessions(self) -> list[dict]:
        async with self._lock:
            return [
                {
                    "id": s.id,
                    "backend": s.backend,
                    "msg_count": s.msg_count,
                    "created_at": s.created_at,
                    "last_active": s.last_active,
                    "in_use": s.in_use,
                }
                for s in self._sessions.values()
            ]

    async def _cleanup(self) -> None:
        while True:
            await asyncio.sleep(300)
            async with self._lock:
                now = time.time()
                expired = [
                    sid
                    for sid, s in self._sessions.items()
                    if now - s.last_active > config.SESSION_TTL and not s.in_use
                ]
                for sid in expired:
                    del self._sessions[sid]
                    logger.info("Session %s expired (TTL)", sid)

    def start_cleanup_task(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup())
            logger.info("Session cleanup task started")

    def stop_cleanup_task(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("Session cleanup task stopped")


session_manager = SessionManager()