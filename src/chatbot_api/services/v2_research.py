from __future__ import annotations

from chatbot_api.adapters.factory import get_adapter
from chatbot_api.schemas import ResearchRequest, ResearchResponse
from chatbot_api.services.domain_policy import domain_policy
from chatbot_api.services.tenant_settings import tenant_settings_service


class V2ResearchService:
    """Skeleton V2 research provider for staged rollout.

    This provider keeps /v2/research stable while we gate V2 and progressively
    switch to the full external provider.
    """

    def __init__(self) -> None:
        self.adapter = get_adapter()

    def research(self, request: ResearchRequest) -> ResearchResponse:
        in_scope, domain = domain_policy.is_query_in_scope(request.tenant_id, request.query.lower())
        if not in_scope:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail=f"Out-of-domain query. This website supports only {domain}-related queries.",
            )

        user_context = self.adapter.get_user_context(user_id=request.user_id, tenant_id=request.tenant_id)
        runtime_settings = tenant_settings_service.get_settings(request.tenant_id)
        name = user_context.get("name", "there")
        overview = user_context.get("overview", "Current account overview is unavailable.")
        improvements = user_context.get("improvements", [])

        summary = f"{name}, here is a concise V2 overview for '{request.query}': {overview}"
        recommendations = list(improvements[: runtime_settings.max_recommendations])
        if not recommendations:
            recommendations = ["No personalized actions found yet. Add account activity and retry."]

        explanation = None
        if request.verbose or runtime_settings.response_style == "detailed":
            explanation = (
                "This response is from the V2 skeleton provider. It uses your tenant/user context and "
                "domain policy, then prioritizes concise, action-oriented guidance."
            )

        return ResearchResponse(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            summary=summary,
            recommendations=recommendations,
            explanation=explanation,
            confidence_score=0.62,
            warnings=["v2_provider:skeleton"],
        )


v2_research_service = V2ResearchService()
