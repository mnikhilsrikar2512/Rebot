import time
from types import MethodType

import jwt
from fastapi.testclient import TestClient

from chatbot_api.config import settings
from chatbot_api.main import app
from chatbot_api.schemas import TenantRuntimeSettingsPatch
from chatbot_api.services.rate_limiter import rate_limiter
from chatbot_api.services.webhook_runtime import webhook_runtime
from chatbot_api.services.external_research import _SourceResult, external_research_service
from chatbot_api.services.tenant_settings import tenant_settings_service
from chatbot_api.services.website_rag import website_rag_service

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


def auth_header_with_role(tenant_id: str, user_id: str, role: str) -> dict[str, str]:
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


def test_login_with_credentials_sets_cookie() -> None:
    from chatbot_api.services.auth_service import auth_service

    original_authenticate = auth_service.authenticate
    original_secret = settings.jwt_secret
    settings.jwt_secret = settings.jwt_secret or "test-jwt-secret-32-bytes-minimum-key"
    auth_service.authenticate = lambda tenant_id, email, password: {
        "tenant_id": tenant_id,
        "user_id": "2",
        "role": "user",
        "name": "John Doe",
        "email": email,
    }
    try:
        response = client.post(
            "/v1/auth/login",
            json={"tenant_id": "tnt_demo", "email": "john@test.local", "password": "User@123"},
        )
        assert response.status_code == 200
        assert response.cookies.get("access_token")
        payload = response.json()
        assert payload["user_id"] == "2"
    finally:
        settings.jwt_secret = original_secret
        auth_service.authenticate = original_authenticate


def test_jwt_claim_mapping_with_existing_site_claims() -> None:
    original_secret = settings.jwt_secret
    original_allow_dev = settings.allow_dev_token_auth
    original_claim_tenant = settings.jwt_claim_tenant_id
    original_claim_user = settings.jwt_claim_user_id
    original_claim_role = settings.jwt_claim_role
    original_sub_fallback = settings.jwt_claim_sub_fallback_enabled

    settings.jwt_secret = "test-jwt-secret-32-bytes-minimum-key"
    settings.allow_dev_token_auth = False
    settings.jwt_claim_tenant_id = "org_id"
    settings.jwt_claim_user_id = "uid"
    settings.jwt_claim_role = "permissions_role"
    settings.jwt_claim_sub_fallback_enabled = True

    token = jwt.encode(
        {
            "org_id": "tnt_demo",
            "uid": "usr_alex",
            "permissions_role": "user",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = client.post(
            "/v1/chat",
            headers=headers,
            json={
                "message": {"role": "user", "content": "give my overview"},
                "stream": False,
            },
        )
        assert response.status_code == 200
        assert str(response.json()["session_id"]).startswith("ses_")
    finally:
        settings.jwt_secret = original_secret
        settings.allow_dev_token_auth = original_allow_dev
        settings.jwt_claim_tenant_id = original_claim_tenant
        settings.jwt_claim_user_id = original_claim_user
        settings.jwt_claim_role = original_claim_role
        settings.jwt_claim_sub_fallback_enabled = original_sub_fallback


def test_local_login_can_be_disabled_for_integrated_mode() -> None:
    original = settings.local_login_enabled
    settings.local_login_enabled = False
    try:
        response = client.post(
            "/v1/auth/login",
            json={"tenant_id": "tnt_demo", "email": "john@test.local", "password": "User@123"},
        )
        assert response.status_code == 403
        assert "Local login is disabled" in response.json()["error"]["message"]
    finally:
        settings.local_login_enabled = original


def test_session_create_and_chat_with_noisy_text() -> None:
    headers = auth_header("tnt_demo", "usr_alex")

    create = client.post(
        "/v1/sessions",
        headers=headers,
        json={"tenant_id": "tnt_demo", "user_id": "usr_alex", "channel": "web"},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": "gve my acnt overveiw and hw to do bttr"},
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["needs_clarification"] is False
    assert "Alex" in payload["message"]["content"]
    assert payload["usage"]["model"] == "qwen2.5-7b-instruct"


def test_v1_chat_verbose_true_adds_explanation() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    create = client.post(
        "/v1/sessions",
        headers=headers,
        json={"tenant_id": "tnt_demo", "user_id": "usr_alex", "channel": "web"},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": "give my overview"},
            "stream": False,
            "verbose": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "Explanation:" in payload["message"]["content"]


def test_chat_auto_creates_session_when_missing() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "message": {"role": "user", "content": "give my overview"},
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert str(payload["session_id"]).startswith("ses_")


def test_chat_uses_auth_scope_when_tenant_user_not_provided() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "message": {"role": "user", "content": "give my overview"},
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert str(payload["session_id"]).startswith("ses_")


def test_scope_isolation_rejects_mismatched_user() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    response = client.post(
        "/v1/sessions",
        headers=headers,
        json={"tenant_id": "tnt_demo", "user_id": "usr_riya", "channel": "web"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "FORBIDDEN"


def test_non_admin_cannot_request_platform_scope() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    create = client.post(
        "/v1/sessions",
        headers=headers,
        json={"tenant_id": "tnt_demo", "user_id": "usr_alex", "channel": "web"},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": "give platform overview for all users"},
            "stream": False,
        },
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "FORBIDDEN"
    assert "Admin access required" in payload["error"]["message"]


def test_chat_streaming_sse_events() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    create = client.post(
        "/v1/sessions",
        headers=headers,
        json={"tenant_id": "tnt_demo", "user_id": "usr_alex", "channel": "web"},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    with client.stream(
        "POST",
        "/v1/chat",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "session_id": session_id,
            "message": {"role": "user", "content": "gve my acnt overveiw"},
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        content = "".join(response.iter_text())

    assert "event: response.started" in content
    assert "event: response.delta" in content
    assert "event: response.completed" in content


def test_rate_limit_returns_429_with_retry_after() -> None:
    original = (
        rate_limiter.enabled,
        rate_limiter.window_seconds,
        rate_limiter.global_limit,
        rate_limiter.chat_limit,
    )
    rate_limiter.configure(enabled=True, window_seconds=60, global_limit=100, chat_limit=1)
    rate_limiter.reset()
    try:
        headers = auth_header("tnt_demo", "usr_alex")
        create = client.post(
            "/v1/sessions",
            headers=headers,
            json={"tenant_id": "tnt_demo", "user_id": "usr_alex", "channel": "web"},
        )
        assert create.status_code == 200
        session_id = create.json()["session_id"]

        first = client.post(
            "/v1/chat",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "session_id": session_id,
                "message": {"role": "user", "content": "give my overview"},
                "stream": False,
            },
        )
        assert first.status_code == 200

        second = client.post(
            "/v1/chat",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "session_id": session_id,
                "message": {"role": "user", "content": "give my overview"},
                "stream": False,
            },
        )
        assert second.status_code == 429
        payload = second.json()
        assert payload["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert payload["error"].get("retry_after_ms", 0) > 0
    finally:
        rate_limiter.configure(
            enabled=original[0],
            window_seconds=original[1],
            global_limit=original[2],
            chat_limit=original[3],
        )
        rate_limiter.reset()


def test_tool_runtime_register_and_invoke() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    register = client.post(
        "/v1/tools/register",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "tools": [
                {
                    "name": "recommend_budget",
                    "description": "Suggest budget changes",
                    "input_schema": {"type": "object", "properties": {"month": {"type": "string"}}},
                    "timeout_ms": 1500,
                    "allowed_roles": ["user", "admin"],
                }
            ],
        },
    )
    assert register.status_code == 200

    invoke = client.post(
        "/v1/tools/invoke",
        headers=headers,
        json={
            "tenant_id": "tnt_demo",
            "user_id": "usr_alex",
            "tool_name": "recommend_budget",
            "params": {"month": "2026-04"},
        },
    )
    assert invoke.status_code == 200
    payload = invoke.json()
    assert payload["tool_name"] == "recommend_budget"
    assert payload["status"] == "success"


def test_webhook_dead_letter_is_recorded() -> None:
    previous_attempts = webhook_runtime.max_attempts
    webhook_runtime.max_attempts = 1
    try:
        headers = auth_header("tnt_demo", "usr_alex")
        register = client.post(
            "/v1/webhooks",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "event": "chat.completed",
                "callback_url": "http://127.0.0.1:9/unreachable",
                "secret": "testsecret",
            },
        )
        assert register.status_code == 200

        create = client.post(
            "/v1/sessions",
            headers=headers,
            json={"tenant_id": "tnt_demo", "user_id": "usr_alex", "channel": "web"},
        )
        assert create.status_code == 200
        session_id = create.json()["session_id"]

        chat = client.post(
            "/v1/chat",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "session_id": session_id,
                "message": {"role": "user", "content": "give my overview"},
                "stream": False,
            },
        )
        assert chat.status_code == 200

        time.sleep(0.2)
        dead = client.get(
            "/v1/webhooks/dead-letters",
            headers=headers,
            params={"tenant_id": "tnt_demo"},
        )
        assert dead.status_code == 200
        items = dead.json()["dead_letters"]
        assert any(item["event"] == "chat.completed" for item in items)
    finally:
        webhook_runtime.max_attempts = previous_attempts


def test_metrics_endpoint_returns_tenant_counters() -> None:
    headers = auth_header("tnt_demo", "usr_alex")
    response = client.get("/v1/metrics", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "total_requests" in payload
    assert payload["tenant"]["tenant_id"] == "tnt_demo"


def test_prometheus_metrics_endpoint_returns_text_payload() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "chatbot_requests_total" in body
    assert "chatbot_errors_total" in body


def test_alerts_endpoint_reports_threshold_breach() -> None:
    old_error_threshold = settings.alert_error_rate_percent_threshold
    old_latency_threshold = settings.alert_avg_latency_ms_threshold
    settings.alert_error_rate_percent_threshold = 0.0
    settings.alert_avg_latency_ms_threshold = 0.0
    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.get("/v1/alerts", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["tenant_id"] == "tnt_demo"
        assert isinstance(payload["alerts"], list)
        assert len(payload["alerts"]) >= 1
    finally:
        settings.alert_error_rate_percent_threshold = old_error_threshold
        settings.alert_avg_latency_ms_threshold = old_latency_threshold


def test_v2_research_returns_concise_recommendations_without_citations() -> None:
    original_allowlist = settings.external_research_allowlist
    original_enabled = settings.external_research_enabled
    original_fetch = external_research_service._fetch_source
    original_v2_enabled = settings.enable_v2
    original_v2_provider = settings.v2_research_provider

    def fake_fetch(self, url, query_terms):
        return _SourceResult(
            url=url,
            title="Trusted Finance Guide",
            text="Diversify allocations and track cash flow weekly.",
            relevance=0.82,
        )

    settings.external_research_enabled = True
    settings.external_research_allowlist = "example.com"
    settings.enable_v2 = True
    settings.v2_research_provider = "external"
    external_research_service._fetch_source = MethodType(fake_fetch, external_research_service)

    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "How can I improve monthly cash flow?",
                "sources": [{"url": "https://example.com/guide"}],
                "max_sources": 3,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["confidence_score"] > 0
        assert len(payload["recommendations"]) >= 1
        assert "citations" not in payload
        assert payload.get("explanation") in (None, "")
    finally:
        settings.external_research_allowlist = original_allowlist
        settings.external_research_enabled = original_enabled
        settings.enable_v2 = original_v2_enabled
        settings.v2_research_provider = original_v2_provider
        external_research_service._fetch_source = original_fetch


def test_v2_research_verbose_true_returns_explanation() -> None:
    original_allowlist = settings.external_research_allowlist
    original_enabled = settings.external_research_enabled
    original_fetch = external_research_service._fetch_source
    original_v2_enabled = settings.enable_v2
    original_v2_provider = settings.v2_research_provider

    def fake_fetch(self, url, query_terms):
        return _SourceResult(
            url=url,
            title="Trusted Finance Guide",
            text="Diversify allocations and track cash flow weekly.",
            relevance=0.82,
        )

    settings.external_research_enabled = True
    settings.external_research_allowlist = "example.com"
    settings.enable_v2 = True
    settings.v2_research_provider = "external"
    external_research_service._fetch_source = MethodType(fake_fetch, external_research_service)

    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "Improve monthly cash flow",
                "sources": [{"url": "https://example.com/guide"}],
                "max_sources": 3,
                "verbose": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("explanation")
    finally:
        settings.external_research_allowlist = original_allowlist
        settings.external_research_enabled = original_enabled
        settings.enable_v2 = original_v2_enabled
        settings.v2_research_provider = original_v2_provider
        external_research_service._fetch_source = original_fetch


def test_v2_research_invalid_provider_returns_500() -> None:
    old_enabled = settings.enable_v2
    old_provider = settings.v2_research_provider
    settings.enable_v2 = True
    settings.v2_research_provider = "bad-provider"
    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "Improve monthly cash flow",
                "sources": [{"url": "https://example.com/guide"}],
            },
        )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    finally:
        settings.enable_v2 = old_enabled
        settings.v2_research_provider = old_provider


def test_v2_research_all_sources_failed_returns_503() -> None:
    original_allowlist = settings.external_research_allowlist
    original_enabled = settings.external_research_enabled
    original_fetch = external_research_service._fetch_source
    original_v2_enabled = settings.enable_v2
    original_v2_provider = settings.v2_research_provider

    def always_fail_fetch(self, url, query_terms):
        raise TimeoutError("timed out")

    settings.external_research_enabled = True
    settings.external_research_allowlist = "example.com"
    settings.enable_v2 = True
    settings.v2_research_provider = "external"
    external_research_service._fetch_source = MethodType(always_fail_fetch, external_research_service)

    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "Improve monthly cash flow",
                "sources": [{"url": "https://example.com/guide"}],
                "max_sources": 2,
            },
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    finally:
        settings.external_research_allowlist = original_allowlist
        settings.external_research_enabled = original_enabled
        settings.enable_v2 = original_v2_enabled
        settings.v2_research_provider = original_v2_provider
        external_research_service._fetch_source = original_fetch


def test_v2_research_rejects_invalid_source_url_scheme() -> None:
    original_enabled = settings.external_research_enabled
    original_v2_enabled = settings.enable_v2
    original_v2_provider = settings.v2_research_provider
    settings.external_research_enabled = True
    settings.enable_v2 = True
    settings.v2_research_provider = "external"
    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "Improve monthly cash flow",
                "sources": [{"url": "file:///tmp/x"}],
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_REQUEST"
    finally:
        settings.external_research_enabled = original_enabled
        settings.enable_v2 = original_v2_enabled
        settings.v2_research_provider = original_v2_provider


def test_v2_research_tenant_scope_mismatch_returns_403() -> None:
    old_enabled = settings.enable_v2
    old_provider = settings.v2_research_provider
    settings.enable_v2 = True
    settings.v2_research_provider = "skeleton"
    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_other",
                "user_id": "usr_alex",
                "query": "give my overview",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
    finally:
        settings.enable_v2 = old_enabled
        settings.v2_research_provider = old_provider


def test_admin_can_patch_and_read_runtime_settings() -> None:
    admin_headers = auth_header_with_role("tnt_demo", "usr_admin", "admin")
    original = tenant_settings_service.get_settings("tnt_demo")
    try:
        patch = client.patch(
            "/v1/admin/settings",
            headers=admin_headers,
            json={
                "tenant_id": "tnt_demo",
                "response_style": "detailed",
                "max_recommendations": 2,
                "show_verdict": True,
                "v2_enabled": True,
                "v2_provider": "skeleton",
            },
        )
        assert patch.status_code == 200
        payload = patch.json()
        assert payload["response_style"] == "detailed"
        assert payload["max_recommendations"] == 2
        assert payload["v2_enabled"] is True

        get_resp = client.get("/v1/admin/settings", headers=admin_headers, params={"tenant_id": "tnt_demo"})
        assert get_resp.status_code == 200
        current = get_resp.json()
        assert current["max_recommendations"] == 2
    finally:
        tenant_settings_service.update_settings(
            TenantRuntimeSettingsPatch(
                tenant_id="tnt_demo",
                response_style=original.response_style,
                max_recommendations=original.max_recommendations,
                show_verdict=original.show_verdict,
                v2_enabled=original.v2_enabled,
                v2_provider=original.v2_provider,
            )
        )


def test_non_admin_cannot_patch_runtime_settings() -> None:
    user_headers = auth_header_with_role("tnt_demo", "usr_alex", "user")
    response = client.patch(
        "/v1/admin/settings",
        headers=user_headers,
        json={
            "tenant_id": "tnt_demo",
            "response_style": "concise",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_v2_research_returns_structured_improvements_minimum_three() -> None:
    original_allowlist = settings.external_research_allowlist
    original_enabled = settings.external_research_enabled
    original_fetch = external_research_service._fetch_source
    original_v2_enabled = settings.enable_v2
    original_v2_provider = settings.v2_research_provider

    def fake_fetch(self, url, query_terms):
        return _SourceResult(
            url=url,
            title="Finance Pattern Guide",
            text="Use contextual nudges and weekly review loops.",
            relevance=0.8,
        )

    settings.external_research_enabled = True
    settings.external_research_allowlist = "example.com"
    settings.enable_v2 = True
    settings.v2_research_provider = "external"
    external_research_service._fetch_source = MethodType(fake_fetch, external_research_service)

    try:
        headers = auth_header("tnt_demo", "usr_alex")
        response = client.post(
            "/v2/research",
            headers=headers,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "how can i improve cash flow",
                "sources": [{"url": "https://example.com/guide"}],
                "rag_context": "Current website page shows user monthly spending and budget summary widgets.",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] in {"improvement", "research", "recommendation"}
        assert payload["source_priority"] == "primary_plus_secondary"
        assert isinstance(payload.get("improvements"), list)
        assert len(payload["improvements"]) >= 3
        first = payload["improvements"][0]
        for key in [
            "area",
            "observation",
            "why_it_matters",
            "industry_insight",
            "recommendation",
            "expected_impact",
            "priority",
        ]:
            assert key in first
    finally:
        settings.external_research_allowlist = original_allowlist
        settings.external_research_enabled = original_enabled
        settings.enable_v2 = original_v2_enabled
        settings.v2_research_provider = original_v2_provider
        external_research_service._fetch_source = original_fetch


def test_admin_can_index_website_content() -> None:
    admin_headers = auth_header_with_role("tnt_demo", "usr_admin", "admin")
    original_fetch = website_rag_service._fetch_html

    def fake_fetch(url: str, timeout: float = 8.0) -> str:
        return """
        <html><head><title>Finance Home</title></head>
        <body>
          <a href='/budget'>Budget</a>
          <p>Monthly cash flow dashboard with budget widgets and savings nudges.</p>
        </body></html>
        """

    website_rag_service._fetch_html = fake_fetch  # type: ignore[method-assign]
    try:
        response = client.post(
            "/v1/admin/website/index",
            headers=admin_headers,
            json={
                "tenant_id": "tnt_demo",
                "website_url": "https://example.com",
                "max_pages": 2,
                "max_depth": 1,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["pages_indexed"] >= 1
        assert payload["chunks_indexed"] >= 1

        stats = client.get(
            "/v1/admin/website/index",
            headers=admin_headers,
            params={"tenant_id": "tnt_demo"},
        )
        assert stats.status_code == 200
        assert stats.json()["chunks_indexed"] >= 1
    finally:
        website_rag_service._fetch_html = original_fetch  # type: ignore[method-assign]
        website_rag_service.clear_tenant("tnt_demo")
