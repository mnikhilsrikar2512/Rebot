from chatbot_api.services.website_rag import collect_website_evidence, website_rag_service


def test_collect_website_evidence_uses_seeded_runtime_context() -> None:
    tenant_id = "tnt_demo"
    website_rag_service.clear_tenant(tenant_id)
    evidence = collect_website_evidence(
        tenant_id=tenant_id,
        query="cash flow improvements",
        domain_type="finance",
        current_page="https://example.com/dashboard",
        rag_context="This page shows monthly cash flow and budget utilization widgets.",
    )
    assert evidence.domain_type == "finance"
    assert evidence.current_page == "https://example.com/dashboard"
    assert isinstance(evidence.snippets, list)
    assert len(evidence.snippets) >= 1
    website_rag_service.clear_tenant(tenant_id)


def test_ingest_site_respects_allowed_domains() -> None:
    tenant_id = "tnt_demo"
    website_rag_service.clear_tenant(tenant_id)
    stats = website_rag_service.ingest_site(
        tenant_id=tenant_id,
        website_url="https://blocked.example.com",
        allowed_domains=["allowed.example.com"],
        max_pages=1,
        max_depth=0,
    )
    assert stats["pages_indexed"] == 0
    assert stats["chunks_indexed"] == 0
