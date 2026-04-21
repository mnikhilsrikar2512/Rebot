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
from chatbot_api.schemas import ResearchRequest, ResearchResponse
from chatbot_api.services.domain_policy import domain_policy
from chatbot_api.services.tenant_settings import tenant_settings_service


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

    def _validate_source(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise HTTPException(status_code=400, detail=f"Invalid source URL scheme: {url}")

        host = (parsed.hostname or "").lower()
        if not host:
            raise HTTPException(status_code=400, detail=f"Invalid source URL host: {url}")

        allowlist = _allowed_domains()
        if allowlist and host not in allowlist:
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

        in_scope, domain = domain_policy.is_query_in_scope(request.tenant_id, request.query.lower())
        if not in_scope:
            raise HTTPException(
                status_code=403,
                detail=f"Out-of-domain query. This website supports only {domain}-related queries.",
            )

        user_context = self.adapter.get_user_context(user_id=request.user_id, tenant_id=request.tenant_id)
        runtime_settings = tenant_settings_service.get_settings(request.tenant_id)
        query_terms = _keyword_set(request.query)

        source_inputs = request.sources[: request.max_sources]
        if not source_inputs:
            raise HTTPException(status_code=400, detail="At least one source URL is required")

        results: list[_SourceResult] = []
        warnings: list[str] = []
        for source in source_inputs:
            self._validate_source(source.url)
            try:
                result = self._fetch_source(source.url, query_terms=query_terms)
                results.append(result)
            except Exception:
                warnings.append(f"source_fetch_failed:{source.url}")

        if not results:
            raise HTTPException(status_code=503, detail="No external sources could be fetched")

        results.sort(key=lambda item: item.relevance, reverse=True)
        top = results[: request.max_sources]

        def asks_explanation(query: str) -> bool:
            q = query.lower()
            explanation_terms = ["explain", "why", "details", "detailed", "how exactly", "breakdown"]
            return any(term in q for term in explanation_terms)

        avg_relevance = sum(item.relevance for item in top) / max(1, len(top))
        confidence = round(min(0.98, 0.45 + avg_relevance * 0.5), 2)

        name = user_context.get("name", "there")
        overview = user_context.get("overview", "Current account overview is unavailable.")
        improvements = user_context.get("improvements", [])

        summary = f"{name}, priority improvement: focus on the top two actions below for {request.query.lower()}."

        recommendations: list[str] = []
        recommendations.extend(improvements[:2])

        for citation in top[:2]:
            if citation.title:
                recommendations.append(
                    f"Apply guidance from '{citation.title}' this week and review impact after 7 days."
                )

        if not recommendations:
            recommendations.append("No tailored recommendation generated. Add more trusted sources and retry.")

        explanation = None
        if request.verbose or asks_explanation(request.query) or runtime_settings.response_style == "detailed":
            source_hint = top[0].title or "trusted source"
            explanation = (
                f"You are currently at: {overview}. The suggested actions are prioritized because they align with "
                f"your account pattern and matched guidance from {source_hint}. Start with the first action, "
                "measure weekly, then adjust."
            )

        return ResearchResponse(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            summary=summary,
            recommendations=recommendations[: runtime_settings.max_recommendations],
            explanation=explanation,
            confidence_score=confidence,
            warnings=warnings,
        )


external_research_service = ExternalResearchService()
