from __future__ import annotations

from typing import Literal


IntentType = Literal[
    "informational",
    "recommendation",
    "improvement",
    "audit",
    "troubleshooting",
    "research",
]


IMPROVEMENT_TERMS = {
    "improve",
    "betterment",
    "optimize",
    "optimization",
    "industry standard",
    "best practices",
    "how do other websites do this",
    "research similar websites",
}

AUDIT_TERMS = {"audit", "review", "gap", "assessment"}
TROUBLESHOOT_TERMS = {"error", "issue", "bug", "broken", "not working", "fix"}
RECOMMEND_TERMS = {"recommend", "suggest", "advice", "what should", "choose", "which option", "best option"}
RESEARCH_TERMS = {"benchmark", "research", "compare", "patterns"}


def classify_intent(query: str) -> IntentType:
    text = (query or "").strip().lower()

    if any(term in text for term in RECOMMEND_TERMS):
        return "recommendation"
    if any(term in text for term in RESEARCH_TERMS):
        return "research"
    if any(term in text for term in IMPROVEMENT_TERMS):
        return "improvement"
    if any(term in text for term in AUDIT_TERMS):
        return "audit"
    if any(term in text for term in TROUBLESHOOT_TERMS):
        return "troubleshooting"
    return "informational"
