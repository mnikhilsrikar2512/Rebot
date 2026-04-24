from __future__ import annotations

import json
from urllib.parse import urlparse

from chatbot_api.config import settings
from chatbot_api.schemas import WebsitePreset


DEFAULT_PRESETS: list[WebsitePreset] = [
    WebsitePreset(
        preset_id="domain_fintech",
        label="Fintech (Open Source)",
        website_url="https://www.fineract.apache.org",
        source_urls=["https://www.fineract.apache.org/", "https://www.fineract.apache.org/docs/current/"],
        allowed_domains=["www.fineract.apache.org"],
        domain_type_hint="fintech",
        site_metadata="Open-source core banking and financial services platform ecosystem.",
        navigation_context="About, Documentation, APIs, Community",
        product_service_context="Banking workflows, lending, payments, and account management",
        rag_context="Fintech platform context for money management and financial workflow suggestions.",
        opensource_repo="https://github.com/apache/fineract",
    ),
    WebsitePreset(
        preset_id="domain_e_commerce",
        label="E-commerce (Open Source)",
        website_url="https://docs.medusajs.com",
        source_urls=["https://docs.medusajs.com", "https://docs.medusajs.com/resources/commerce-modules/cart"],
        allowed_domains=["docs.medusajs.com", "medusajs.com"],
        domain_type_hint="e_commerce",
        site_metadata="Open-source commerce framework docs with cart, checkout, and product modules.",
        navigation_context="Storefront, Cart, Checkout, Products, Admin, Integrations",
        product_service_context="Composable ecommerce platform and APIs",
        rag_context="E-commerce flow context for product discovery, cart, and checkout optimization.",
        opensource_repo="https://github.com/medusajs/medusa",
    ),
    WebsitePreset(
        preset_id="domain_saas",
        label="SaaS (Open Source)",
        website_url="https://www.appwrite.io",
        source_urls=["https://www.appwrite.io/docs", "https://www.appwrite.io/docs/products/auth"],
        allowed_domains=["www.appwrite.io", "appwrite.io"],
        domain_type_hint="saas",
        site_metadata="Open-source backend-as-a-service platform with auth, databases, and functions.",
        navigation_context="Docs, Products, Auth, Databases, Functions, Integrations",
        product_service_context="SaaS platform workflows, onboarding, and developer integrations",
        rag_context="SaaS context for onboarding, activation, and feature adoption improvements.",
        opensource_repo="https://github.com/appwrite/appwrite",
    ),
    WebsitePreset(
        preset_id="domain_education",
        label="Education (Open Source)",
        website_url="https://docs.moodle.org",
        source_urls=["https://docs.moodle.org", "https://docs.moodle.org/404/en/Courses"],
        allowed_domains=["docs.moodle.org", "moodle.org"],
        domain_type_hint="education",
        site_metadata="Open-source learning platform documentation for courses, students, and instructors.",
        navigation_context="Courses, Lessons, Users, Grading, Administration",
        product_service_context="Learning management workflows",
        rag_context="Education context for learning paths and course completion improvements.",
        opensource_repo="https://github.com/moodle/moodle",
    ),
    WebsitePreset(
        preset_id="domain_healthcare",
        label="Healthcare (Open Source)",
        website_url="https://openmrs.org",
        source_urls=["https://openmrs.org", "https://openmrs.org/about/"],
        allowed_domains=["openmrs.org", "talk.openmrs.org"],
        domain_type_hint="healthcare",
        site_metadata="Open-source medical record system platform and community resources.",
        navigation_context="About, Implementations, Community, Resources",
        product_service_context="Healthcare information systems and care workflows",
        rag_context="Healthcare platform context for patient and clinic workflow guidance.",
        opensource_repo="https://github.com/openmrs/openmrs-core",
    ),
    WebsitePreset(
        preset_id="domain_real_estate",
        label="Real Estate (Open Data Ecosystem)",
        website_url="https://www.openstreetmap.org",
        source_urls=["https://www.openstreetmap.org", "https://wiki.openstreetmap.org/wiki/Main_Page"],
        allowed_domains=["www.openstreetmap.org", "wiki.openstreetmap.org"],
        domain_type_hint="real_estate",
        site_metadata="Open mapping and location ecosystem used for property and geospatial discovery workflows.",
        navigation_context="Map, Search, Layers, Community, Wiki",
        product_service_context="Property/location discovery and mapping workflows",
        rag_context="Real estate style discovery context for listings and location exploration journeys.",
        opensource_repo="https://github.com/openstreetmap/openstreetmap-website",
    ),
    WebsitePreset(
        preset_id="domain_travel_hospitality",
        label="Travel & Hospitality (Open Source)",
        website_url="https://www.opentripplanner.org",
        source_urls=["https://www.opentripplanner.org", "https://docs.opentripplanner.org/en/latest/"],
        allowed_domains=["www.opentripplanner.org", "docs.opentripplanner.org"],
        domain_type_hint="travel_hospitality",
        site_metadata="Open-source trip planning platform for routes, itineraries, and transit journeys.",
        navigation_context="Overview, Documentation, Routing, Itineraries, APIs",
        product_service_context="Travel planning and booking-adjacent journey optimization",
        rag_context="Travel context for itinerary clarity and conversion-friendly planning flows.",
        opensource_repo="https://github.com/opentripplanner/OpenTripPlanner",
    ),
    WebsitePreset(
        preset_id="domain_food_restaurant",
        label="Food & Restaurant (Open Source)",
        website_url="https://docs.tandoor.dev",
        source_urls=["https://docs.tandoor.dev", "https://docs.tandoor.dev/features/"],
        allowed_domains=["docs.tandoor.dev", "tandoor.dev"],
        domain_type_hint="food_restaurant",
        site_metadata="Open-source food and recipe platform documentation with meal workflows.",
        navigation_context="Recipes, Meals, Shopping, Features, Setup",
        product_service_context="Food discovery, planning, and ordering-style workflow guidance",
        rag_context="Food and meal management context for menu and ordering journey improvements.",
        opensource_repo="https://github.com/TandoorRecipes/recipes",
    ),
    WebsitePreset(
        preset_id="domain_media_content",
        label="Media & Content (Open Source)",
        website_url="https://ghost.org",
        source_urls=["https://ghost.org/docs", "https://ghost.org/help/"],
        allowed_domains=["ghost.org"],
        domain_type_hint="media_content",
        site_metadata="Open-source publishing platform for blogs, newsletters, and media content.",
        navigation_context="Docs, Publishing, Themes, Memberships, Integrations",
        product_service_context="Content creation, publishing, and audience growth workflows",
        rag_context="Media platform context for content discovery and engagement improvements.",
        opensource_repo="https://github.com/TryGhost/Ghost",
    ),
    WebsitePreset(
        preset_id="domain_social_community",
        label="Social / Community (Open Source)",
        website_url="https://www.discourse.org",
        source_urls=["https://www.discourse.org", "https://meta.discourse.org"],
        allowed_domains=["www.discourse.org", "meta.discourse.org"],
        domain_type_hint="social_community",
        site_metadata="Open-source community discussion platform with moderation and engagement tools.",
        navigation_context="Community, Topics, Categories, Moderation, Trust Levels",
        product_service_context="Forum and community engagement platform",
        rag_context="Community platform context for onboarding, moderation, and participation flow.",
        opensource_repo="https://github.com/discourse/discourse",
    ),
    WebsitePreset(
        preset_id="domain_government_ngo",
        label="Government / NGO (Open Source)",
        website_url="https://ckan.org",
        source_urls=["https://ckan.org", "https://docs.ckan.org/en/latest/"],
        allowed_domains=["ckan.org", "docs.ckan.org"],
        domain_type_hint="government_ngo",
        site_metadata="Open-source data portal ecosystem used by governments and nonprofits.",
        navigation_context="About, Features, Documentation, Extensions",
        product_service_context="Public services data access and open governance workflows",
        rag_context="Government and NGO context for service discovery and information clarity improvements.",
        opensource_repo="https://github.com/ckan/ckan",
    ),
    WebsitePreset(
        preset_id="domain_other",
        label="Other (Open Knowledge)",
        website_url="https://www.wikipedia.org",
        source_urls=["https://www.wikipedia.org", "https://www.wikidata.org/wiki/Wikidata:Main_Page"],
        allowed_domains=["www.wikipedia.org", "www.wikidata.org"],
        domain_type_hint="other",
        site_metadata="General-purpose open knowledge websites.",
        navigation_context="Articles, Topics, Search, Community",
        product_service_context="General information and navigation guidance",
        rag_context="Fallback context for general website analysis.",
        opensource_repo="https://github.com/wikimedia/mediawiki",
    ),
]


def list_website_presets() -> list[WebsitePreset]:
    raw = getattr(settings, "website_presets_json", "")
    if not raw:
        return DEFAULT_PRESETS

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return DEFAULT_PRESETS
        presets: list[WebsitePreset] = []
        for item in parsed:
            if isinstance(item, dict):
                presets.append(WebsitePreset(**item))
        return presets or DEFAULT_PRESETS
    except Exception:
        return DEFAULT_PRESETS


def _parse_tenant_preset_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in (raw or "").split(","):
        item = part.strip()
        if not item or ":" not in item:
            continue
        tenant_id, preset_id = item.split(":", 1)
        mapping[tenant_id.strip()] = preset_id.strip()
    return mapping


def _normalize_domain(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def get_website_preset(preset_id: str) -> WebsitePreset | None:
    for preset in list_website_presets():
        if preset.preset_id == preset_id:
            return preset
    return None


def resolve_website_preset(
    tenant_id: str,
    preferred_domain: str | None = None,
    preferred_preset_id: str | None = None,
    preferred_website_url: str | None = None,
) -> WebsitePreset | None:
    presets = list_website_presets()
    if not presets:
        return None

    tenant_map = _parse_tenant_preset_map(settings.website_preset_map)
    mapped_preset_id = tenant_map.get(tenant_id)
    if mapped_preset_id:
        preset = get_website_preset(mapped_preset_id)
        if preset:
            return preset

    normalized_domain = _normalize_domain(preferred_domain)
    if normalized_domain:
        for preset in presets:
            if _normalize_domain(preset.domain_type_hint) == normalized_domain:
                return preset

    return presets[0]
    if preferred_preset_id:
        preset = get_website_preset(preferred_preset_id)
        if preset:
            return preset

    if preferred_website_url:
        host = (urlparse(preferred_website_url).hostname or "").lower()
        if host:
            for preset in presets:
                if host in {domain.lower() for domain in preset.allowed_domains}:
                    return preset
