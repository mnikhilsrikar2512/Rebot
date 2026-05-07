from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MethodType

import jwt
from fastapi.testclient import TestClient

from chatbot_api.config import settings
from chatbot_api.main import app
from chatbot_api.schemas import TenantRuntimeSettingsPatch
from chatbot_api.services.external_research import _SourceResult, external_research_service
from chatbot_api.services.tenant_settings import tenant_settings_service
from chatbot_api.services.website_rag import website_rag_service


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def _auth_header(tenant_id: str, user_id: str, role: str = "admin") -> dict[str, str]:
    settings.jwt_secret = settings.jwt_secret or "test-jwt-secret-32-bytes-minimum-key"
    settings.allow_dev_token_auth = False
    token = jwt.encode(
        {"tenant_id": tenant_id, "user_id": user_id, "role": role},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    client = TestClient(app)
    checks: list[CheckResult] = []

    old_enable_v2 = settings.enable_v2
    old_provider = settings.v2_research_provider
    old_ext_enabled = settings.external_research_enabled
    old_allowlist = settings.external_research_allowlist
    old_fetch = external_research_service._fetch_source

    settings.enable_v2 = True
    settings.external_research_enabled = True
    settings.external_research_allowlist = "example.com,finly.example.com,docs.finly.example.com"

    def fake_fetch(self, url, query_terms):
        return _SourceResult(
            url=url,
            title="Internal UX Pattern Note",
            text="Budget nudges and clear category insights improve task completion.",
            relevance=0.86,
        )

    external_research_service._fetch_source = MethodType(fake_fetch, external_research_service)

    headers_admin = _auth_header("tnt_demo", "usr_admin", role="admin")
    headers_user = _auth_header("tnt_demo", "usr_alex", role="user")

    ctx = {
        "website_url": "https://finly.example.com",
        "allowed_domains": ["finly.example.com", "docs.finly.example.com", "example.com"],
        "domain_type_hint": "fintech",
        "site_metadata": "Finly helps users track expenses and improve monthly cash flow.",
        "navigation_context": "Dashboard, Budgets, Transactions, Goals, Help",
        "current_page": "https://finly.example.com/dashboard",
        "current_page_context": "Dashboard shows spend by category and monthly net.",
        "product_service_context": "Budget planner and savings goal tools",
        "rag_context": "Users can monitor monthly budget utilization and set savings targets.",
    }

    try:
        tenant_settings_service.update_settings(
            TenantRuntimeSettingsPatch(
                tenant_id="tnt_demo",
                website_url="https://finly.example.com",
                allowed_domains=["finly.example.com", "docs.finly.example.com", "example.com"],
                source_urls=["https://example.com/guide"],
                domain_type_hint="fintech",
            )
        )

        # 1) Website indexing
        website_rag_service.clear_tenant("tnt_demo")
        response = client.post(
            "/v1/admin/website/index",
            headers=headers_admin,
            json={
                "tenant_id": "tnt_demo",
                "website_url": "https://example.com",
                "allowed_domains": ["example.com"],
                "max_pages": 2,
                "max_depth": 1,
            },
        )
        checks.append(
            CheckResult(
                "admin website index endpoint",
                response.status_code == 200,
                f"status={response.status_code}",
            )
        )

        # 2) V2 skeleton mode matrix sample
        settings.v2_research_provider = "skeleton"
        r1 = client.post(
            "/v2/research",
            headers=headers_user,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "How can I improve budget flow?",
                **ctx,
            },
        )
        body1 = r1.json() if r1.headers.get("content-type", "").startswith("application/json") else {}
        checks.append(
            CheckResult(
                "v2 skeleton improvement mode",
                r1.status_code == 200 and body1.get("response_mode") == "improvement" and len(body1.get("improvements", [])) >= 3,
                f"status={r1.status_code}, mode={body1.get('response_mode')}, improvements={len(body1.get('improvements', []))}",
            )
        )

        # 3) V2 external mode matrix sample
        settings.v2_research_provider = "external"
        r2 = client.post(
            "/v2/research",
            headers=headers_user,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "Summarize budget dashboard patterns from these sources.",
                "sources": [{"url": "https://example.com/guide"}],
                "max_sources": 2,
                **ctx,
            },
        )
        body2 = r2.json() if r2.headers.get("content-type", "").startswith("application/json") else {}
        checks.append(
            CheckResult(
                "v2 external research mode",
                r2.status_code == 200 and body2.get("response_mode") == "content_summarization" and body2.get("source_priority") == "primary_plus_secondary",
                f"status={r2.status_code}, mode={body2.get('response_mode')}, source_priority={body2.get('source_priority')}",
            )
        )

        # 4) Out-of-scope strict refusal
        r3 = client.post(
            "/v2/research",
            headers=headers_user,
            json={
                "tenant_id": "tnt_demo",
                "user_id": "usr_alex",
                "query": "What are the best football tactics?",
                **ctx,
            },
        )
        body3 = r3.json() if r3.headers.get("content-type", "").startswith("application/json") else {}
        checks.append(
            CheckResult(
                "out-of-scope refusal",
                r3.status_code == 200 and body3.get("response_mode") == "out_of_scope",
                f"status={r3.status_code}, mode={body3.get('response_mode')}",
            )
        )

    finally:
        external_research_service._fetch_source = old_fetch
        settings.enable_v2 = old_enable_v2
        settings.v2_research_provider = old_provider
        settings.external_research_enabled = old_ext_enabled
        settings.external_research_allowlist = old_allowlist
        website_rag_service.clear_tenant("tnt_demo")

    passed = all(item.passed for item in checks)
    output = {
        "passed": passed,
        "checks": [item.__dict__ for item in checks],
    }
    out_file = Path("/tmp/chatbot_smoke_report.json")
    out_file.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("Production Readiness Smoke Report")
    print("---------------------------------")
    for item in checks:
        mark = "PASS" if item.passed else "FAIL"
        print(f"[{mark}] {item.name} - {item.details}")
    print(f"overall: {'PASS' if passed else 'FAIL'}")
    print(f"report: {out_file}")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
