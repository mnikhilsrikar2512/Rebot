from chatbot_api.schemas import Message


class MemoryStore:
    """No-op store: chat content is never persisted."""

    def append(
        self,
        session_id: str,
        message: Message,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        return None

    def get(self, session_id: str) -> list[Message]:
        return []


memory_store = MemoryStore()
