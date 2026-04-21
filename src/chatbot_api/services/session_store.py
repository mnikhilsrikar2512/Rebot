from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from chatbot_api.config import settings
from chatbot_api.schemas import SessionResponse


class SessionStore:
    def __init__(self) -> None:
        self._memory: dict[str, SessionResponse] = {}
        self._engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        if not self._engine or self._schema_ready:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    IF OBJECT_ID('dbo.chatbot_sessions', 'U') IS NULL
                    BEGIN
                        CREATE TABLE dbo.chatbot_sessions (
                            session_id NVARCHAR(100) NOT NULL PRIMARY KEY,
                            tenant_id NVARCHAR(100) NOT NULL,
                            user_id NVARCHAR(100) NOT NULL,
                            channel NVARCHAR(50) NOT NULL,
                            created_at DATETIME2 NOT NULL,
                            ttl_seconds INT NOT NULL,
                            memory_config NVARCHAR(MAX) NOT NULL
                        );
                        CREATE INDEX IX_chatbot_sessions_tenant ON dbo.chatbot_sessions(tenant_id);
                    END
                    """
                )
            )
        self._schema_ready = True

    def create(self, session: SessionResponse) -> None:
        if self._engine:
            self._ensure_schema()
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO dbo.chatbot_sessions
                            (session_id, tenant_id, user_id, channel, created_at, ttl_seconds, memory_config)
                        VALUES
                            (:session_id, :tenant_id, :user_id, :channel, :created_at, :ttl_seconds, :memory_config)
                        """
                    ),
                    {
                        "session_id": session.session_id,
                        "tenant_id": session.tenant_id,
                        "user_id": session.user_id,
                        "channel": session.channel,
                        "created_at": datetime.now(timezone.utc),
                        "ttl_seconds": session.ttl_seconds,
                        "memory_config": json.dumps(session.memory_config),
                    },
                )
            return
        self._memory[session.session_id] = session

    def get(self, session_id: str) -> SessionResponse | None:
        if self._engine:
            self._ensure_schema()
            with self._engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT session_id, tenant_id, user_id, channel, created_at, ttl_seconds, memory_config
                        FROM dbo.chatbot_sessions
                        WHERE session_id = :session_id
                        """
                    ),
                    {"session_id": session_id},
                ).mappings().first()
            if not row:
                return None
            memory_config_raw = row["memory_config"]
            memory_config = json.loads(memory_config_raw) if memory_config_raw else {}
            return SessionResponse(
                session_id=row["session_id"],
                tenant_id=row["tenant_id"],
                user_id=row["user_id"],
                channel=row["channel"],
                created_at=row["created_at"].isoformat() if row["created_at"] else datetime.now(timezone.utc).isoformat(),
                ttl_seconds=int(row["ttl_seconds"]),
                memory_config=memory_config,
            )
        return self._memory.get(session_id)

    def count_by_tenant(self, tenant_id: str) -> int:
        if self._engine:
            self._ensure_schema()
            with self._engine.connect() as conn:
                value = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS total
                        FROM dbo.chatbot_sessions
                        WHERE tenant_id = :tenant_id
                        """
                    ),
                    {"tenant_id": tenant_id},
                ).scalar_one()
            return int(value or 0)
        return sum(1 for s in self._memory.values() if s.tenant_id == tenant_id)


session_store = SessionStore()
