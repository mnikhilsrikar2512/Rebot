from __future__ import annotations

from functools import lru_cache
import re

from sqlalchemy import create_engine, text

from chatbot_api.config import settings
from chatbot_api.services.tenant_settings import tenant_settings_service


DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "finance": {
        "finance",
        "budget",
        "income",
        "expense",
        "saving",
        "savings",
        "cashflow",
        "transaction",
        "debt",
        "investment",
        "inflation",
        "spend",
        "spending",
        "loan",
        "credit",
        "balance",
        "category",
    },
    "event": {
        "event",
        "events",
        "ticket",
        "tickets",
        "attendee",
        "venue",
        "schedule",
        "speaker",
        "registration",
        "checkin",
        "rsvp",
        "session",
        "agenda",
    },
    "food": {
        "food",
        "menu",
        "order",
        "orders",
        "dish",
        "recipe",
        "kitchen",
        "restaurant",
        "delivery",
        "ingredient",
        "calorie",
        "meal",
    },
    "fintech": {
        "finance",
        "banking",
        "payment",
        "wallet",
        "budget",
        "expense",
        "savings",
        "cashflow",
        "loan",
        "credit",
    },
    "e_commerce": {
        "shop",
        "store",
        "product",
        "catalog",
        "cart",
        "checkout",
        "order",
        "shipping",
    },
    "saas": {
        "software",
        "dashboard",
        "integration",
        "workflow",
        "subscription",
        "feature",
    },
}

DOMAIN_ALIASES: dict[str, str] = {
    "finance": "fintech",
    "banking": "fintech",
    "e-commerce": "e_commerce",
    "ecommerce": "e_commerce",
    "software": "saas",
}

GENERIC_WEBSITE_TERMS = {
    "website",
    "app",
    "account",
    "dashboard",
    "profile",
    "settings",
    "overview",
    "how",
    "help",
    "report",
    "improve",
    "change",
    "suggest",
    "suggestion",
    "improvements",
    "overviews",
    "month",
    "monthly",
    "week",
    "weekly",
    "next",
    "step",
    "steps",
    "action",
    "actions",
    "plan",
    "roadmap",
    "priority",
}


def _tokenize(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
    expanded: set[str] = set(tokens)
    for token in tokens:
        if token.endswith("ing") and len(token) > 5:
            expanded.add(token[:-3])
        if token.endswith("ed") and len(token) > 4:
            expanded.add(token[:-2])
        if token.endswith("s") and len(token) > 3:
            expanded.add(token[:-1])
    return expanded


def _matches_terms(tokens: set[str], terms: set[str]) -> bool:
    if tokens.intersection(terms):
        return True
    for token in tokens:
        for term in terms:
            if token.startswith(term) or term.startswith(token):
                return True
    return False


def _parse_tenant_domain_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in (raw or "").split(","):
        text = part.strip()
        if not text or ":" not in text:
            continue
        tenant, domain = text.split(":", 1)
        mapping[tenant.strip()] = domain.strip().lower()
    return mapping


class DomainPolicy:
    def __init__(self) -> None:
        self._static_map = _parse_tenant_domain_map(settings.tenant_domain_map)
        self._engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
        self._has_profiles_table = self._check_profiles_table()

    def _check_profiles_table(self) -> bool:
        if not self._engine:
            return False
        with self._engine.connect() as conn:
            value = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = 'chatbot_tenant_profiles'
                    """
                )
            ).scalar_one()
        return bool(value)

    @lru_cache(maxsize=256)
    def get_tenant_domain(self, tenant_id: str) -> str | None:
        runtime_domain = tenant_settings_service.get_settings(tenant_id).domain_type_hint
        if runtime_domain:
            return str(runtime_domain).strip().lower().replace("-", "_").replace(" ", "_")

        if tenant_id in self._static_map:
            return self._static_map[tenant_id]

        if self._engine and self._has_profiles_table:
            with self._engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT TOP 1 domain
                        FROM chatbot_tenant_profiles
                        WHERE tenant_id = :tenant_id
                        """
                    ),
                    {"tenant_id": tenant_id},
                ).mappings().first()
            if row and row.get("domain"):
                return str(row["domain"]).strip().lower()

        return settings.default_domain.lower() if settings.default_domain else None

    def is_query_in_scope(self, tenant_id: str, normalized_query: str) -> tuple[bool, str | None]:
        domain = self.get_tenant_domain(tenant_id)
        if not domain:
            return True, None

        normalized_domain = domain.strip().lower().replace("-", "_").replace(" ", "_")
        normalized_domain = DOMAIN_ALIASES.get(normalized_domain, normalized_domain)

        words = _tokenize(normalized_query)
        if _matches_terms(words, GENERIC_WEBSITE_TERMS):
            return True, normalized_domain

        domain_terms = DOMAIN_KEYWORDS.get(normalized_domain, set())
        if not domain_terms:
            return True, normalized_domain

        return _matches_terms(words, domain_terms), normalized_domain


domain_policy = DomainPolicy()
