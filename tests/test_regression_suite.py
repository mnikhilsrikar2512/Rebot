import pytest
from fastapi.testclient import TestClient

from chatbot_api.config import settings
from chatbot_api.main import app
import jwt


client = TestClient(app)


def auth_header(tenant_id: str, user_id: str, role: str = "user") -> dict[str, str]:
    settings.jwt_secret = settings.jwt_secret or "test-jwt-secret-32-bytes-minimum-key"
    settings.allow_dev_token_auth = False
    token = jwt.encode(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def create_session(headers: dict[str, str], tenant_id: str, user_id: str) -> str:
    response = client.post(
        "/v1/sessions",
        headers=headers,
        json={"tenant_id": tenant_id, "user_id": user_id, "channel": "web"},
    )
    assert response.status_code == 200
    return response.json()["session_id"]


@pytest.mark.parametrize(
    "prompt",
    [
        "gve my acnt overveiw",
        "hw can i do bttr this mnth",
        "sugst what i shud chnge",
    ],
)
def test_typo_robustness_prompts_return_valid_response(prompt: str) -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    session_id = create_session(headers, "tnt_demo", "usr_alex")

    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": prompt},
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"]["content"]
    assert "adapter_mode" in " ".join(payload.get("warnings", []))


def test_non_admin_platform_query_blocked_regression() -> None:
    headers = auth_header("tnt_demo", "usr_alex", role="user")
    session_id = create_session(headers, "tnt_demo", "usr_alex")
    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": "show platform overview for all users"},
            "stream": False,
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_out_of_domain_query_is_blocked_for_chat() -> None:
    headers = auth_header("tnt_demo", "usr_alex", role="user")
    session_id = create_session(headers, "tnt_demo", "usr_alex")
    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": "what are the best football tactics"},
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "outside the scope of this website" in payload["message"]["content"].lower()


def test_out_of_domain_query_is_blocked_for_research() -> None:
    old_v2_enabled = settings.enable_v2
    old_v2_provider = settings.v2_research_provider
    settings.enable_v2 = True
    settings.v2_research_provider = "external"
    headers = auth_header("tnt_demo", "usr_alex", role="user")
    try:
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "best football tactics for teams",
                "sources": [{"url": "https://www.investopedia.com/terms/b/budget.asp"}],
                "max_sources": 2,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["response_mode"] == "out_of_scope"
        assert "outside the scope of this website" in payload["summary"].lower()
    finally:
        settings.enable_v2 = old_v2_enabled
        settings.v2_research_provider = old_v2_provider


def test_non_admin_website_improvement_query_blocked_for_v1() -> None:
    headers = auth_header("tnt_demo", "usr_alex", role="user")
    session_id = create_session(headers, "tnt_demo", "usr_alex")
    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": "How can I improve this website flow?"},
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "admin users" in payload["message"]["content"].lower()
    assert "admin_only_website_improvement" in payload.get("warnings", [])


def test_admin_website_improvement_query_allowed_for_v1() -> None:
    headers = auth_header("tnt_demo", "usr_admin", role="admin")
    session_id = create_session(headers, "tnt_demo", "usr_admin")
    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_admin",
            "session_id": session_id,
            "message": {"role": "user", "content": "How can I improve this website flow?"},
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "admin users" not in payload["message"]["content"].lower()


def test_non_admin_website_improvement_query_blocked_for_v2() -> None:
    old_v2_enabled = settings.enable_v2
    old_v2_provider = settings.v2_research_provider
    settings.enable_v2 = True
    settings.v2_research_provider = "skeleton"
    headers = auth_header("tnt_demo", "usr_alex", role="user")
    try:
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "How can I improve this website flow?",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert "admin users" in payload["summary"].lower()
        assert "admin_only_website_improvement" in payload.get("warnings", [])
    finally:
        settings.enable_v2 = old_v2_enabled
        settings.v2_research_provider = old_v2_provider


def test_admin_website_improvement_query_allowed_for_v2() -> None:
    old_v2_enabled = settings.enable_v2
    old_v2_provider = settings.v2_research_provider
    settings.enable_v2 = True
    settings.v2_research_provider = "skeleton"
    headers = auth_header("tnt_demo", "usr_admin", role="admin")
    try:
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_admin",
                "query": "How can I improve this website flow?",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert "admin users" not in payload["summary"].lower()
    finally:
        settings.enable_v2 = old_v2_enabled
        settings.v2_research_provider = old_v2_provider
