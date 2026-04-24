from __future__ import annotations

import re


BLOCKED_BRAND_TERMS = {
    "amazon",
    "stripe",
    "shopify",
    "paypal",
    "google",
    "meta",
    "netflix",
}


def enforce_pattern_only_language(text: str, allow_brands: bool = False) -> str:
    if allow_brands:
        return text

    lowered = text.lower()
    if any(term in lowered for term in BLOCKED_BRAND_TERMS):
        text = re.sub(
            r"\b(Amazon|Stripe|Shopify|PayPal|Google|Meta|Netflix)\b",
            "leading platforms",
            text,
            flags=re.IGNORECASE,
        )
    return text
