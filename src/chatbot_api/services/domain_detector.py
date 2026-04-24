from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DomainProfile:
    primary_domain: str
    aliases: set[str]
    keywords: set[str]
    intent_capabilities: list[str]
    allowed_behaviors: list[str]


DOMAIN_TAXONOMY: dict[str, DomainProfile] = {
    "fintech": DomainProfile(
        primary_domain="fintech",
        aliases={"finance", "banking", "payments", "wallet"},
        keywords={
            "finance",
            "fintech",
            "bank",
            "banking",
            "payment",
            "wallet",
            "loan",
            "credit",
            "debit",
            "budget",
            "expense",
            "savings",
            "investment",
            "money",
            "cashflow",
        },
        intent_capabilities=["guidance", "recommendation", "optimization", "audit"],
        allowed_behaviors=["budget guidance", "financial workflow suggestions", "ux improvement"],
    ),
    "insurance": DomainProfile(
        primary_domain="insurance",
        aliases={"insurtech"},
        keywords={"insurance", "policy", "premium", "claim", "coverage", "underwriting", "beneficiary"},
        intent_capabilities=["guidance", "comparison", "recommendation"],
        allowed_behaviors=["coverage explanation", "policy journey improvement"],
    ),
    "investment_trading": DomainProfile(
        primary_domain="investment_trading",
        aliases={"trading", "investing", "brokerage", "forex", "stocks", "crypto"},
        keywords={"stock", "portfolio", "asset", "trading", "broker", "market", "forex", "crypto", "fund"},
        intent_capabilities=["research", "comparison", "recommendation"],
        allowed_behaviors=["platform flow suggestion", "education and risk-aware guidance"],
    ),
    "e_commerce": DomainProfile(
        primary_domain="e_commerce",
        aliases={"ecommerce", "shop", "store", "d2c", "dropshipping"},
        keywords={"shop", "product", "catalog", "cart", "checkout", "order", "sku", "store", "shipping"},
        intent_capabilities=["shopping", "recommendation", "optimization"],
        allowed_behaviors=["conversion improvement", "catalog and checkout UX suggestions"],
    ),
    "marketplace": DomainProfile(
        primary_domain="marketplace",
        aliases={"multi_vendor", "multivendor", "vendor"},
        keywords={"marketplace", "seller", "vendor", "buyer", "listing", "commission", "merchant"},
        intent_capabilities=["recommendation", "optimization", "audit"],
        allowed_behaviors=["buyer/seller journey suggestions", "trust and conversion improvements"],
    ),
    "saas": DomainProfile(
        primary_domain="saas",
        aliases={"software", "b2b", "platform"},
        keywords={"saas", "software", "dashboard", "workspace", "integration", "subscription", "feature", "onboarding"},
        intent_capabilities=["guidance", "troubleshooting", "optimization", "audit"],
        allowed_behaviors=["feature discovery suggestions", "activation and retention improvements"],
    ),
    "developer_tools": DomainProfile(
        primary_domain="developer_tools",
        aliases={"api", "sdk", "docs", "documentation"},
        keywords={"api", "sdk", "docs", "documentation", "endpoint", "cli", "library", "developer"},
        intent_capabilities=["guidance", "troubleshooting", "research"],
        allowed_behaviors=["developer-experience suggestions", "integration guidance"],
    ),
    "education": DomainProfile(
        primary_domain="education",
        aliases={"edtech", "lms", "learning", "school", "university"},
        keywords={"course", "lesson", "learn", "student", "teacher", "class", "curriculum", "quiz", "education"},
        intent_capabilities=["guidance", "recommendation", "optimization"],
        allowed_behaviors=["learning path improvements", "completion and engagement suggestions"],
    ),
    "healthcare": DomainProfile(
        primary_domain="healthcare",
        aliases={"medical", "health", "wellness", "mental_health", "fitness"},
        keywords={"patient", "clinic", "doctor", "appointment", "medical", "health", "treatment", "wellness"},
        intent_capabilities=["guidance", "navigation_help", "troubleshooting"],
        allowed_behaviors=["care-journey UX suggestions", "information clarity improvements"],
    ),
    "real_estate": DomainProfile(
        primary_domain="real_estate",
        aliases={"property", "rental", "housing"},
        keywords={"property", "listing", "rent", "rental", "broker", "real", "estate", "mortgage"},
        intent_capabilities=["recommendation", "comparison", "optimization"],
        allowed_behaviors=["listing discovery improvements", "lead conversion suggestions"],
    ),
    "travel_hospitality": DomainProfile(
        primary_domain="travel_hospitality",
        aliases={"travel", "hospitality", "booking"},
        keywords={"travel", "booking", "hotel", "itinerary", "trip", "flight", "reservation", "destination"},
        intent_capabilities=["recommendation", "troubleshooting", "optimization"],
        allowed_behaviors=["booking flow suggestions", "trust and transparency improvements"],
    ),
    "food_restaurant": DomainProfile(
        primary_domain="food_restaurant",
        aliases={"food", "restaurant", "delivery"},
        keywords={"restaurant", "menu", "order", "delivery", "meal", "kitchen", "food", "reservation"},
        intent_capabilities=["recommendation", "optimization", "audit"],
        allowed_behaviors=["menu discovery suggestions", "ordering flow improvements"],
    ),
    "media_content": DomainProfile(
        primary_domain="media_content",
        aliases={"media", "content", "news", "blog"},
        keywords={"article", "news", "blog", "podcast", "video", "content", "editorial"},
        intent_capabilities=["informational", "research", "optimization"],
        allowed_behaviors=["content discovery suggestions", "engagement improvements"],
    ),
    "social_community": DomainProfile(
        primary_domain="social_community",
        aliases={"social", "community", "forum", "network"},
        keywords={"community", "social", "forum", "discussion", "post", "member", "follow", "network"},
        intent_capabilities=["recommendation", "moderation", "optimization"],
        allowed_behaviors=["community health suggestions", "onboarding and retention improvements"],
    ),
    "government_ngo": DomainProfile(
        primary_domain="government_ngo",
        aliases={"government", "public_services", "ngo", "nonprofit"},
        keywords={"government", "citizen", "public", "service", "benefit", "ngo", "donation", "policy"},
        intent_capabilities=["navigation_help", "informational", "optimization"],
        allowed_behaviors=["service access guidance", "public information UX improvements"],
    ),
    "event_management": DomainProfile(
        primary_domain="event_management",
        aliases={"events", "ticketing"},
        keywords={"event", "ticket", "attendee", "venue", "speaker", "registration", "schedule", "agenda"},
        intent_capabilities=["recommendation", "troubleshooting", "optimization"],
        allowed_behaviors=["registration and event-flow improvements"],
    ),
    "other": DomainProfile(
        primary_domain="other",
        aliases={"general"},
        keywords=set(),
        intent_capabilities=["informational", "guidance"],
        allowed_behaviors=["general website guidance"],
    ),
}


def _normalize_domain_label(label: str) -> str:
    normalized = (label or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in DOMAIN_TAXONOMY:
        return normalized
    for key, profile in DOMAIN_TAXONOMY.items():
        if normalized in profile.aliases:
            return key
    return normalized


def classify_domain(
    domain_hint: str | None,
    website_url: str | None,
    site_metadata: str | None,
    navigation_context: str | None,
    product_service_context: str | None,
    rag_snippets: list[str],
) -> dict[str, object]:
    if domain_hint:
        hinted = _normalize_domain_label(domain_hint)
        if hinted in DOMAIN_TAXONOMY:
            profile = DOMAIN_TAXONOMY[hinted]
            return {
                "primary_domain": profile.primary_domain,
                "secondary_domain": None,
                "intent_capabilities": profile.intent_capabilities,
                "allowed_behaviors": profile.allowed_behaviors,
                "note": None,
            }

    corpus = " ".join(
        [website_url or "", site_metadata or "", navigation_context or "", product_service_context or "", " ".join(rag_snippets or [])]
    ).lower()
    tokens = re.findall(r"[a-zA-Z_]{2,}", corpus)

    scores: list[tuple[int, str]] = []
    for domain, profile in DOMAIN_TAXONOMY.items():
        if domain == "other":
            continue
        score = sum(1 for token in tokens if token in profile.keywords or token in profile.aliases)
        scores.append((score, domain))
    scores.sort(reverse=True)

    if not scores or scores[0][0] == 0:
        fallback = DOMAIN_TAXONOMY["other"]
        return {
            "primary_domain": fallback.primary_domain,
            "secondary_domain": None,
            "intent_capabilities": fallback.intent_capabilities,
            "allowed_behaviors": fallback.allowed_behaviors,
            "note": "Based on available website signals, this appears to be a general-purpose website.",
        }

    primary = scores[0][1]
    secondary = scores[1][1] if len(scores) > 1 and scores[1][0] > 0 else None
    primary_profile = DOMAIN_TAXONOMY[primary]
    note = None
    if scores[0][0] < 3:
        note = f"Based on current website signals, the likely primary domain is {primary_profile.primary_domain}."

    return {
        "primary_domain": primary_profile.primary_domain,
        "secondary_domain": DOMAIN_TAXONOMY[secondary].primary_domain if secondary else None,
        "intent_capabilities": primary_profile.intent_capabilities,
        "allowed_behaviors": primary_profile.allowed_behaviors,
        "note": note,
    }


def detect_domain(
    domain_hint: str | None,
    website_url: str | None,
    site_metadata: str | None,
    navigation_context: str | None,
    product_service_context: str | None,
    rag_snippets: list[str],
) -> tuple[str, str | None, str | None]:
    classification = classify_domain(
        domain_hint=domain_hint,
        website_url=website_url,
        site_metadata=site_metadata,
        navigation_context=navigation_context,
        product_service_context=product_service_context,
        rag_snippets=rag_snippets,
    )
    return (
        str(classification["primary_domain"]),
        str(classification["secondary_domain"]) if classification["secondary_domain"] else None,
        str(classification["note"]) if classification["note"] else None,
    )
