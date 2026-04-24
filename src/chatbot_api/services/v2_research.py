from __future__ import annotations

import re

from chatbot_api.adapters.factory import get_adapter
from chatbot_api.schemas import ImprovementSuggestion, ResearchRequest, ResearchResponse
from chatbot_api.services.domain_detector import detect_domain
from chatbot_api.services.domain_policy import domain_policy
from chatbot_api.services.intent_classifier import classify_intent
from chatbot_api.services.response_formatter import (
    OUT_OF_SCOPE_MESSAGE,
    format_audit_summary,
    format_betterment_plan,
    format_informational,
    format_navigation_help,
    format_recommendation,
    format_research_benchmark,
    format_troubleshooting,
)
from chatbot_api.services.tenant_settings import tenant_settings_service
from chatbot_api.services.website_presets import resolve_website_preset
from chatbot_api.services.website_rag import collect_website_evidence, website_rag_service


class V2ResearchService:
    """Skeleton V2 research provider for staged rollout.

    This provider keeps /v2/research stable while we gate V2 and progressively
    switch to the full external provider.
    """

    def __init__(self) -> None:
        self.adapter = get_adapter()

    @staticmethod
    def _is_admin(role: str | None) -> bool:
        return (role or "").strip().lower() == "admin"

    @staticmethod
    def _is_website_improvement_request(intent: str, query: str) -> bool:
        normalized = (query or "").lower()
        website_terms = {"website", "site", "page", "ui", "ux", "navigation"}
        improvement_terms = {"improve", "improvement", "optimize", "optimization", "audit", "better", "fix"}
        tokens = set(normalized.split())
        if tokens.intersection(website_terms) and tokens.intersection(improvement_terms):
            return True
        trigger_terms = ["improve website", "improve this website", "website flow", "site flow", "audit website"]
        return any(term in normalized for term in trigger_terms)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

    @classmethod
    def _dedupe_recommendations(cls, items: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            key = cls._normalize_text(item)
            if not key or key in seen:
                continue
            seen.add(key)
            output.append(item.strip())
        return output

    def research(self, request: ResearchRequest) -> ResearchResponse:
        intent = classify_intent(request.query)
        in_scope, domain = domain_policy.is_query_in_scope(request.tenant_id, request.query.lower())
        response_mode = {
            "informational": "informational",
            "recommendation": "recommendation",
            "improvement": "improvement",
            "audit": "audit",
            "troubleshooting": "troubleshooting",
            "research": "content_summarization",
        }.get(intent, "informational")
        if not in_scope:
            return ResearchResponse(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                intent=intent,
                domain=domain,
                source_priority="primary_only",
                response_mode="out_of_scope",
                summary=OUT_OF_SCOPE_MESSAGE,
                recommendations=[],
                improvements=[],
                explanation=None,
                confidence_score=0.99,
                warnings=[f"domain_scope_blocked:{domain}", "v2_provider:skeleton"],
            )

        if not self._is_admin(request.user_role) and self._is_website_improvement_request(intent, request.query):
            return ResearchResponse(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                intent=intent,
                domain=domain,
                source_priority="primary_only",
                response_mode="informational",
                summary=(
                    "I can help with using this website and completing tasks. "
                    "Website improvement and audit suggestions are available only to admin users."
                ),
                recommendations=[],
                improvements=[],
                explanation=None,
                confidence_score=0.9,
                warnings=["admin_only_website_improvement"],
            )

        user_context = self.adapter.get_user_context(user_id=request.user_id, tenant_id=request.tenant_id)
        runtime_settings = tenant_settings_service.get_settings(request.tenant_id)
        preset = resolve_website_preset(
            tenant_id=request.tenant_id,
            preferred_domain=runtime_settings.domain_type_hint or request.domain_type_hint or request.domain_type or domain,
            preferred_preset_id=runtime_settings.website_preset_id,
            preferred_website_url=runtime_settings.website_url,
        )
        configured_source_urls = runtime_settings.source_urls or []
        effective_website_url = runtime_settings.website_url or request.website_url or (preset.website_url if preset else None)
        effective_domain_hint = (
            runtime_settings.domain_type_hint
            or request.domain_type_hint
            or request.domain_type
            or (preset.domain_type_hint if preset else None)
            or domain
        )
        effective_current_page = (
            request.current_page
            or (configured_source_urls[0] if configured_source_urls else None)
            or ((preset.source_urls[0] if preset and preset.source_urls else None))
        )
        effective_site_metadata = request.site_metadata or (preset.site_metadata if preset else None)
        effective_navigation_context = request.navigation_context or (preset.navigation_context if preset else None)
        effective_product_service_context = request.product_service_context or (preset.product_service_context if preset else None)
        effective_rag_context = (
            request.rag_context
            or (preset.rag_context if preset else None)
            or effective_site_metadata
            or effective_navigation_context
            or effective_product_service_context
            or request.current_page_context
        )

        if effective_website_url and website_rag_service.stats(request.tenant_id).get("chunks_indexed", 0) == 0:
            try:
                website_rag_service.ingest_site(
                    tenant_id=request.tenant_id,
                    website_url=effective_website_url,
                    allowed_domains=runtime_settings.allowed_domains or (preset.allowed_domains if preset else []),
                    max_pages=4,
                    max_depth=1,
                )
            except Exception:
                pass

        evidence = collect_website_evidence(
            tenant_id=request.tenant_id,
            query=request.query,
            domain_type=effective_domain_hint,
            current_page=effective_current_page,
            rag_context=effective_rag_context,
        )
        detected_domain, _, detection_note = detect_domain(
            domain_hint=effective_domain_hint,
            website_url=effective_website_url,
            site_metadata=effective_site_metadata,
            navigation_context=effective_navigation_context,
            product_service_context=effective_product_service_context,
            rag_snippets=evidence.snippets,
        )
        name = user_context.get("name", "there")
        overview = user_context.get("overview", "Current account overview is unavailable.")
        improvements = user_context.get("improvements", [])

        if evidence.weak_context and intent in {"informational", "recommendation", "troubleshooting"}:
            return ResearchResponse(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                intent=intent,
                domain=detected_domain,
                context_note=detection_note or "Based on available website information.",
                source_priority="primary_only",
                response_mode=response_mode,
                summary="I could not find enough information on this website to answer that confidently.",
                recommendations=[],
                improvements=[],
                explanation=None,
                confidence_score=0.55,
                warnings=["website_context_weak", "v2_provider:skeleton"],
            )

        context_line = f"Current page context: {effective_current_page}." if effective_current_page else "Current page context is limited."
        summary = f"{name}, here is a focused view: {overview} {context_line}"
        recommendations = list(improvements[: runtime_settings.max_recommendations])
        if not recommendations:
            recommendations = ["No personalized actions found yet. Add account activity and retry."]

        recommendations = self._dedupe_recommendations(recommendations)
        fallback_pool = [
            "Set one weekly spending cap and review progress at the end of the week.",
            "Use category-level alerts so users can catch overspending earlier.",
            "Add one clear next-step CTA on key pages to reduce decision friction.",
            "Highlight the top budget risk area first and suggest one immediate action.",
            "Track one success metric (for example budget adherence) for the next 14 days.",
        ]
        for fallback in fallback_pool:
            if len(recommendations) >= 3:
                break
            if self._normalize_text(fallback) not in {self._normalize_text(item) for item in recommendations}:
                recommendations.append(fallback)

        domain_pattern = {
            "fintech": "Most fintech platforms increase completion with contextual nudges and simple action plans.",
            "event": "Most event platforms improve conversion with simplified registration and timely reminders.",
            "food": "Most food platforms improve repeat usage with faster reorder journeys.",
        }.get(detected_domain or "", "Most websites improve outcomes with clearer journeys and guided actions.")

        observation = evidence.snippets[0][:180] if evidence.snippets else "Website context is limited in current retrieval window."
        structured: list[ImprovementSuggestion] = []
        for idx, rec in enumerate(recommendations[: max(3, runtime_settings.max_recommendations)]):
            structured.append(
                ImprovementSuggestion(
                    area=f"Improvement Area {idx + 1}",
                    observation=observation,
                    why_it_matters="This affects user trust, clarity, and completion of key website tasks.",
                    industry_insight=domain_pattern,
                    recommendation=rec,
                    expected_impact="Improved engagement and faster user task completion.",
                    priority="high" if idx == 0 else ("medium" if idx < 3 else "low"),
                )
            )

        explanation = None
        if request.verbose or runtime_settings.response_style == "detailed":
            explanation = (
                "This response is from the V2 skeleton provider. It uses your tenant/user context and "
                "domain policy, then prioritizes concise, action-oriented guidance."
            )

        if intent == "recommendation":
            summary = format_recommendation(
                goal=request.query,
                option_1=(
                    recommendations[0],
                    "Strong alignment with your current context and goal.",
                    "May need additional iteration for best results.",
                ),
                option_2=(
                    recommendations[1] if len(recommendations) > 1 else "Maintain current flow with monitoring",
                    "Low implementation effort.",
                    "Lower immediate upside.",
                ),
                final_recommendation=recommendations[0],
                why_fit="It best aligns with your current context and goal.",
                domain=detected_domain,
            )
        elif intent == "improvement":
            summary = format_betterment_plan(
                items=structured,
                summary="The website can improve task completion and clarity with focused updates.",
                quick_wins=[item.recommendation for item in structured[:3]],
                strategic=[item.recommendation for item in structured[2:]],
                domain=detected_domain,
            )
        elif intent == "research":
            summary = format_research_benchmark(
                current_state=observation,
                patterns=[domain_pattern],
                gaps=["Current flow can better surface next best actions."],
                recommendations=[item.recommendation for item in structured],
                expected_outcome="Higher completion rates and improved user confidence.",
                domain=detected_domain,
            )
        elif intent == "audit":
            summary = format_audit_summary(
                strengths=["Context available", "Domain-safe guidance"],
                weaknesses=["Limited page evidence in current context" if evidence.weak_context else "Minor navigation friction"],
                quick_wins=[structured[0].recommendation],
                strategic=[item.recommendation for item in structured[1:3]],
                domain=detected_domain,
            )
        elif intent == "troubleshooting":
            summary = format_troubleshooting(
                problem="A website workflow issue was reported.",
                causes=[
                    "Navigation path is unclear.",
                    "Required context is incomplete.",
                    "A step in the page journey is being skipped.",
                ],
                steps=[
                    "Open the target section from the website menu.",
                    "Validate required fields and page inputs.",
                    "Retry from a fresh session.",
                ],
                escalation="Contact website support with page URL and request details.",
                domain=detected_domain,
            )
        elif intent == "informational":
            summary = format_informational(summary=summary, support=evidence.current_page, domain=detected_domain)
        else:
            summary = format_navigation_help(
                intent=request.query,
                location=request.current_page or "Website main navigation",
                steps=[
                    "Open the website menu.",
                    "Select the relevant section.",
                    "Follow the page prompts to complete the task.",
                ],
                domain=detected_domain,
            )

        return ResearchResponse(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            intent=intent,
            domain=detected_domain,
            context_note=(detection_note or "Based on available website information.") if evidence.weak_context else detection_note,
            source_priority="primary_only",
            response_mode=response_mode,
            summary=summary,
            recommendations=recommendations,
            improvements=structured,
            explanation=explanation,
            confidence_score=0.62,
            warnings=["v2_provider:skeleton"],
        )


v2_research_service = V2ResearchService()
