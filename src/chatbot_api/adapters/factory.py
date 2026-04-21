from chatbot_api.adapters.base import Adapter
from chatbot_api.adapters.mock_adapter import MockAdapter
from chatbot_api.adapters.sql_adapter import build_sql_adapter
from chatbot_api.config import settings


def get_adapter() -> Adapter:
    sql_adapter = build_sql_adapter()
    if sql_adapter is not None:
        return sql_adapter
    return MockAdapter()


def adapter_mode() -> str:
    return "sqlserver" if settings.database_url else "mock"
