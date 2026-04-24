from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str


class ChatContext(BaseModel):
    locale: str | None = None
    timezone: str | None = None


class ChatRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    message: Message
    channel: str = "web"
    stream: bool = False
    strict_grounding: bool = True
    verbose: bool = False
    context: ChatContext | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    source_type: Literal["tool", "knowledge"]
    source_id: str
    timestamp: str = Field(default_factory=utc_now_iso)


class ResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    citations: list[Citation] = Field(default_factory=list)


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    model: str


class Grounding(BaseModel):
    mode: Literal["client_data_first"] = "client_data_first"
    account_scoped: bool = True


class ChatResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex[:10]}")
    trace_id: str = Field(default_factory=lambda: f"trc_{uuid4().hex[:10]}")
    session_id: str
    message: ResponseMessage
    confidence_score: float
    needs_clarification: bool
    missing_data_fields: list[str] = Field(default_factory=list)
    grounding: Grounding = Field(default_factory=Grounding)
    usage: Usage
    warnings: list[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str | None = None
    channel: str = "web"


class SessionResponse(BaseModel):
    session_id: str
    tenant_id: str
    user_id: str
    channel: str
    created_at: str = Field(default_factory=utc_now_iso)
    ttl_seconds: int = 86400
    memory_config: dict[str, Any] = Field(
        default_factory=lambda: {"max_turns": 20, "summarize_after_turns": 12}
    )


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    timeout_ms: int = 3000
    allowed_roles: list[str] = Field(default_factory=lambda: ["user", "admin", "runtime_service"])


class ToolsRegisterRequest(BaseModel):
    tenant_id: str
    tools: list[ToolDefinition]


class ToolInvokeRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str | None = None
    tool_name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    tool_name: str
    status: str
    output: dict[str, Any]
    duration_ms: int


class WebhookRegistration(BaseModel):
    tenant_id: str
    event: str
    callback_url: str
    secret: str


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex[:10]}")
    retry_after_ms: int | None = None


class LoginRequest(BaseModel):
    tenant_id: str
    email: str
    password: str


class LoginResponse(BaseModel):
    tenant_id: str
    user_id: str
    role: str
    name: str | None = None
    email: str


class ExternalSource(BaseModel):
    url: str
    title: str | None = None
    published_at: str | None = None


class ResearchRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str | None = None
    user_role: str | None = None
    query: str = Field(min_length=3, max_length=500)
    sources: list[ExternalSource] = Field(default_factory=list)
    max_sources: int = Field(default=5, ge=1, le=10)
    verbose: bool = False
    website_url: str | None = None
    allowed_domains: list[str] = Field(default_factory=list)
    domain_type_hint: str | None = None
    domain_type: str | None = None
    rag_context: str | None = None
    site_metadata: str | None = None
    navigation_context: str | None = None
    current_page: str | None = None
    current_page_context: str | None = None
    product_service_context: str | None = None


class ImprovementSuggestion(BaseModel):
    area: str
    observation: str
    why_it_matters: str
    recommendation: str
    expected_impact: str
    priority: Literal["high", "medium", "low"]
    industry_insight: str | None = None


class ResearchResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex[:10]}")
    trace_id: str = Field(default_factory=lambda: f"trc_{uuid4().hex[:10]}")
    tenant_id: str
    user_id: str
    intent: Literal[
        "informational",
        "recommendation",
        "improvement",
        "audit",
        "troubleshooting",
        "research",
    ]
    domain: str | None = None
    context_note: str | None = None
    source_priority: Literal["primary_only", "primary_plus_secondary"] = "primary_only"
    response_mode: Literal[
        "informational",
        "recommendation",
        "improvement",
        "audit",
        "troubleshooting",
        "comparison",
        "navigation_help",
        "content_summarization",
        "out_of_scope",
    ] = "informational"
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    improvements: list[ImprovementSuggestion] = Field(default_factory=list)
    explanation: str | None = None
    confidence_score: float
    warnings: list[str] = Field(default_factory=list)


class TenantRuntimeSettings(BaseModel):
    tenant_id: str
    response_style: Literal["concise", "detailed"] = "concise"
    max_recommendations: int = Field(default=3, ge=1, le=5)
    show_verdict: bool = True
    v2_enabled: bool | None = None
    v2_provider: Literal["skeleton", "external"] | None = None
    website_preset_id: str | None = None
    website_url: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    domain_type_hint: str | None = None


class TenantRuntimeSettingsPatch(BaseModel):
    tenant_id: str
    response_style: Literal["concise", "detailed"] | None = None
    max_recommendations: int | None = Field(default=None, ge=1, le=5)
    show_verdict: bool | None = None
    v2_enabled: bool | None = None
    v2_provider: Literal["skeleton", "external"] | None = None
    website_preset_id: str | None = None
    website_url: str | None = None
    source_urls: list[str] | None = None
    allowed_domains: list[str] | None = None
    domain_type_hint: str | None = None


class WebsiteIndexRequest(BaseModel):
    tenant_id: str
    website_url: str
    allowed_domains: list[str] = Field(default_factory=list)
    max_pages: int = Field(default=8, ge=1, le=50)
    max_depth: int = Field(default=1, ge=0, le=3)


class WebsiteIndexResponse(BaseModel):
    tenant_id: str
    pages_indexed: int
    chunks_indexed: int


class WebsiteAutoIntegrateRequest(BaseModel):
    tenant_id: str
    website_url: str
    max_pages: int = Field(default=8, ge=1, le=50)
    max_depth: int = Field(default=1, ge=0, le=3)


class WebsiteAutoIntegrateResponse(BaseModel):
    tenant_id: str
    website_url: str
    primary_domain: str
    secondary_domain: str | None = None
    preset_id: str | None = None
    pages_indexed: int
    chunks_indexed: int


class WebsitePreset(BaseModel):
    preset_id: str
    label: str
    website_url: str
    source_urls: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    domain_type_hint: str | None = None
    site_metadata: str | None = None
    navigation_context: str | None = None
    product_service_context: str | None = None
    rag_context: str | None = None
    opensource_repo: str | None = None


class DomainClassifyRequest(BaseModel):
    website_url: str | None = None
    domain_hint: str | None = None
    site_metadata: str | None = None
    navigation_context: str | None = None
    product_service_context: str | None = None
    rag_snippets: list[str] = Field(default_factory=list)


class DomainClassifyResponse(BaseModel):
    primary_domain: str
    secondary_domain: str | None = None
    intent_capabilities: list[str] = Field(default_factory=list)
    allowed_behaviors: list[str] = Field(default_factory=list)
    note: str | None = None
