from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from chatbot_api.adapters.factory import get_adapter
from chatbot_api.config import settings
from chatbot_api.schemas import ExternalSource, ImprovementSuggestion, ResearchRequest, ResearchResponse
from chatbot_api.services.domain_detector import detect_domain
from chatbot_api.services.domain_policy import domain_policy
from chatbot_api.services.intent_classifier import classify_intent
from chatbot_api.services.output_policy import enforce_pattern_only_language
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


def _allowed_domains() -> set[str]:
    raw = settings.external_research_allowlist
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _extract_text_from_html(html: str) -> str:
    no_script = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    no_style = re.sub(r"<style[\s\S]*?</style>", " ", no_script, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", no_style)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = unescape(match.group(1)).strip()
    return re.sub(r"\s+", " ", title)


def _keyword_set(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return set(words)


@dataclass
class _SourceResult:
    url: str
    title: str | None
    text: str
    relevance: float


class ExternalResearchService:
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

    def _validate_source(self, url: str, allowed_domains: list[str], website_url: str | None) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise HTTPException(status_code=400, detail=f"Invalid source URL scheme: {url}")

        host = (parsed.hostname or "").lower()
        if not host:
            raise HTTPException(status_code=400, detail=f"Invalid source URL host: {url}")

        allowlist = {d.strip().lower() for d in (allowed_domains or []) if d.strip()}
        if website_url:
            website_host = (urlparse(website_url).hostname or "").lower()
            if website_host:
                allowlist.add(website_host)

        if not allowlist:
            allowlist = _allowed_domains()

        allowed = False
        for item in allowlist:
            if host == item or host.endswith(f".{item}"):
                allowed = True
                break
        if allowlist and not allowed:
            raise HTTPException(status_code=403, detail=f"Source domain not allowed: {host}")

    def _fetch_source(self, url: str, query_terms: set[str]) -> _SourceResult:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text

        title = _extract_title(html)
        text = _extract_text_from_html(html)
        source_terms = _keyword_set(text)

        overlap = query_terms.intersection(source_terms)
        score = round(min(1.0, len(overlap) / max(1, len(query_terms))), 3)
        return _SourceResult(url=url, title=title, text=text, relevance=score)

    def research(self, request: ResearchRequest) -> ResearchResponse:
        if not settings.external_research_enabled:
            raise HTTPException(status_code=403, detail="External research is disabled")

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
                warnings=[f"domain_scope_blocked:{domain}"],
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

        request_source_urls = [source.url for source in request.sources if source.url]
        configured_source_urls = runtime_settings.source_urls or []
        preset_source_urls = preset.source_urls if preset else []
        effective_source_urls = configured_source_urls or request_source_urls or preset_source_urls
        effective_sources = request.sources or [ExternalSource(url=url) for url in effective_source_urls]

        effective_website_url = runtime_settings.website_url or request.website_url or (preset.website_url if preset else None)
        validation_website_url = runtime_settings.website_url or request.website_url or (None if request_source_urls else (preset.website_url if preset else None))
        effective_allowed_domains = runtime_settings.allowed_domains or request.allowed_domains or ([] if request_source_urls else (preset.allowed_domains if preset else []))
        effective_domain_hint = (
            runtime_settings.domain_type_hint
            or request.domain_type_hint
            or request.domain_type
            or (preset.domain_type_hint if preset else None)
            or domain
        )
        effective_current_page = request.current_page or (effective_source_urls[0] if effective_source_urls else None)
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
                    allowed_domains=effective_allowed_domains,
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
        query_terms = _keyword_set(request.query)

        if intent not in {"improvement", "research", "audit", "recommendation"}:
            if evidence.weak_context:
                summary = "I could not find enough information on this website to answer that confidently."
            else:
                summary = format_informational(
                    summary=f"Here is the most relevant context found: {evidence.snippets[0][:240]}",
                    support=evidence.current_page,
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
                recommendations=[],
                improvements=[],
                explanation=None,
                confidence_score=0.66,
                warnings=["website_context_weak"] if evidence.weak_context else [],
            )

        source_inputs = effective_sources[: request.max_sources]

        results: list[_SourceResult] = []
        warnings: list[str] = []
        for source in source_inputs:
            self._validate_source(source.url, effective_allowed_domains, validation_website_url)
            try:
                result = self._fetch_source(source.url, query_terms=query_terms)
                results.append(result)
            except Exception:
                warnings.append(f"source_fetch_failed:{source.url}")

        if source_inputs and not results:
            raise HTTPException(status_code=503, detail="No external sources could be fetched")

        results.sort(key=lambda item: item.relevance, reverse=True)
        top = results[: request.max_sources]

        def asks_explanation(query: str) -> bool:
            q = query.lower()
            explanation_terms = ["explain", "why", "details", "detailed", "how exactly", "breakdown"]
            return any(term in q for term in explanation_terms)

        avg_relevance = sum(item.relevance for item in top) / max(1, len(top)) if top else 0.2
        confidence = round(min(0.98, 0.45 + avg_relevance * 0.5), 2)

        name = user_context.get("name", "there")
        overview = user_context.get("overview", "Current account overview is unavailable.")
        improvements = user_context.get("improvements", [])

        context_line = f"Current page context: {effective_current_page}." if effective_current_page else "Current page context is limited."
        summary = f"{name}, here are focused suggestions for '{request.query.lower()}'. {context_line}"

        recommendations: list[str] = []
        recommendations.extend(improvements[:2])

        for citation in top[:2]:
            if citation.title:
                recommendations.append(
                    f"Apply guidance from '{citation.title}' this week and review impact after 7 days."
                )

        if not recommendations:
            recommendations.append("No tailored recommendation generated. Add more trusted sources and retry.")
        recommendations = self._dedupe_recommendations(recommendations)
        fallback_pool = [
            "Set one measurable weekly goal and review completion after 7 days.",
            "Prioritize one high-friction step and simplify it with clearer prompts.",
            "Use contextual nudges near decision points to improve user completion.",
            "Add a low-effort progress indicator to keep users oriented in the flow.",
            "Track one conversion metric and iterate on the weakest page first.",
        ]
        for fallback in fallback_pool:
            if len(recommendations) >= 3:
                break
            if self._normalize_text(fallback) not in {self._normalize_text(item) for item in recommendations}:
                recommendations.append(fallback)

        pattern_hint = {
            "fintech": "Most fintech platforms improve engagement with proactive budget nudges and savings prompts.",
            "e-commerce": "Most e-commerce stores improve conversion with clearer product hierarchy and simplified checkout.",
            "saas": "Leading SaaS products typically improve activation through guided onboarding and feature discovery.",
            "education": "Education platforms improve completion with clearer learning paths and outcomes messaging.",
            "healthcare": "Healthcare websites improve trust with clearer service details and safer booking flows.",
            "real estate": "Real estate websites improve lead quality through better listing filters and trust indicators.",
            "travel": "Travel platforms improve conversion with transparent pricing and clearer booking steps.",
            "food": "Food platforms improve retention through reorder shortcuts and clearer category journeys.",
        }.get(detected_domain or "", "Most websites improve outcomes through clearer guidance and faster user flows.")

        website_obs = evidence.snippets[0][:180] if evidence.snippets else "Website context is limited in current retrieval window."
        improvements_structured: list[ImprovementSuggestion] = []
        for idx, item in enumerate(recommendations[: max(3, runtime_settings.max_recommendations)]):
            priority = "high" if idx == 0 else ("medium" if idx < 3 else "low")
            improvements_structured.append(
                ImprovementSuggestion(
                    area=f"Improvement Area {idx + 1}",
                    observation=website_obs,
                    why_it_matters="This affects user clarity, trust, and task completion on core website journeys.",
                    industry_insight=enforce_pattern_only_language(pattern_hint),
                    recommendation=enforce_pattern_only_language(item),
                    expected_impact="Higher clarity, stronger engagement, and better goal completion.",
                    priority=priority,
                )
            )

        explanation = None
        if request.verbose or asks_explanation(request.query) or runtime_settings.response_style == "detailed":
            source_hint = top[0].title or "trusted source"
            explanation = (
                f"You are currently at: {overview}. The suggested actions are prioritized because they align with "
                f"your account pattern and matched guidance from {source_hint}. Start with the first action, "
                "measure weekly, then adjust."
            )

        if intent == "recommendation":
            summary = format_recommendation(
                goal=request.query,
                option_1=(
                    recommendations[0],
                    "Strong alignment with your current goal.",
                    "May require iterative tuning.",
                ),
                option_2=(
                    recommendations[1] if len(recommendations) > 1 else "Maintain current approach and monitor",
                    "Lower implementation risk.",
                    "May deliver slower improvement.",
                ),
                final_recommendation=recommendations[0],
                why_fit="It fits your current context and pattern best.",
                domain=detected_domain,
            )
        elif intent == "improvement":
            summary = format_betterment_plan(
                items=improvements_structured,
                summary="The website can improve clarity, trust, and conversion with focused updates.",
                quick_wins=[item.recommendation for item in improvements_structured[:3]],
                strategic=[item.recommendation for item in improvements_structured[2:]],
                domain=detected_domain,
            )
        elif intent == "audit":
            summary = format_audit_summary(
                strengths=["Website context is available", "Domain boundaries enforced"],
                weaknesses=["Some evidence coverage may be limited"],
                quick_wins=[improvements_structured[0].recommendation],
                strategic=[rec.recommendation for rec in improvements_structured[1:3]],
                domain=detected_domain,
            )
        elif intent == "troubleshooting":
            summary = format_troubleshooting(
                problem="A workflow issue was reported.",
                causes=[
                    "Navigation path is unclear for this action.",
                    "Required field or step may be missing.",
                    "User context is incomplete in the current page.",
                ],
                steps=[
                    "Open the relevant section from the main navigation.",
                    "Validate required fields and page context.",
                    "Retry the action from a fresh session.",
                ],
                escalation="Escalate to website support with page URL, timestamp, and request id.",
                domain=detected_domain,
            )
        elif intent == "research":
            summary = format_research_benchmark(
                current_state=website_obs,
                patterns=[pattern_hint],
                gaps=["Current flow can better highlight next best actions."],
                recommendations=[item.recommendation for item in improvements_structured],
                expected_outcome="More consistent user completion and stronger engagement.",
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
                    "Select the section most relevant to your task.",
                    "Follow the page prompts to complete your action.",
                ],
                domain=detected_domain,
            )

        return ResearchResponse(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            intent=intent,
            domain=detected_domain,
            context_note=(detection_note or "Based on available website information.") if evidence.weak_context else detection_note,
            source_priority="primary_plus_secondary" if top else "primary_only",
            response_mode=response_mode,
            summary=summary,
            recommendations=recommendations[: runtime_settings.max_recommendations],
            improvements=improvements_structured[: max(3, runtime_settings.max_recommendations)],
            explanation=explanation,
            confidence_score=confidence,
            warnings=warnings,
        )


external_research_service = ExternalResearchService()
