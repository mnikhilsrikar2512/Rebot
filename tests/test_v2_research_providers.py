from fastapi.testclient import TestClient
import jwt

from chatbot_api.config import settings
from chatbot_api.main import app

client = TestClient(app)


def auth_header(tenant_id: str, user_id: str) -> dict[str, str]:
    settings.jwt_secret = settings.jwt_secret or "test-jwt-secret-32-bytes-minimum-key"
    settings.allow_dev_token_auth = False
    token = jwt.encode(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": "user",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def test_v2_feature_flag_blocks_when_disabled() -> None:
    old_enabled = settings.enable_v2
    old_provider = settings.v2_research_provider
    settings.enable_v2 = False
    settings.v2_research_provider = "skeleton"
    try:
        response = client.post(
            "/v2/research",
            headers=auth_header("tnt_demo", "usr_alex"),
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "give my overview",
            },
        )
        assert response.status_code == 403
    finally:
        settings.enable_v2 = old_enabled
        settings.v2_research_provider = old_provider


def test_v2_skeleton_provider_uses_same_endpoint() -> None:
    old_enabled = settings.enable_v2
    old_provider = settings.v2_research_provider
    settings.enable_v2 = True
    settings.v2_research_provider = "skeleton"
    try:
        response = client.post(
            "/v2/research",
            headers=auth_header("tnt_demo", "usr_alex"),
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "give my overview",
                "verbose": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "recommendations" in data
        assert any(item == "v2_provider:skeleton" for item in data.get("warnings", []))
    finally:
        settings.enable_v2 = old_enabled
        settings.v2_research_provider = old_provider
