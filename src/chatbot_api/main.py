import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from chatbot_api.auth import (
    AuthContext,
    create_access_token,
    enforce_request_scope,
    require_auth,
    try_parse_auth_header,
)
from chatbot_api.adapters.factory import adapter_mode
from chatbot_api.config import settings
from chatbot_api.schemas import (
    ChatRequest,
    ChatResponse,
    DomainClassifyRequest,
    DomainClassifyResponse,
    LoginRequest,
    LoginResponse,
    ResearchRequest,
    SessionCreateRequest,
    SessionResponse,
    TenantRuntimeSettings,
    TenantRuntimeSettingsPatch,
    WebsiteAutoIntegrateRequest,
    WebsiteAutoIntegrateResponse,
    WebsitePreset,
    WebsiteIndexRequest,
    WebsiteIndexResponse,
    ToolInvokeRequest,
    ToolsRegisterRequest,
    WebhookRegistration,
)
from chatbot_api.services.orchestrator import AdapterRuntimeError, AdminScopeError, TenantScopeError, orchestrator
from chatbot_api.services.metrics import metrics_store
from chatbot_api.services.external_research import external_research_service
from chatbot_api.services.v2_research import v2_research_service
from chatbot_api.services.tenant_settings import tenant_settings_service
from chatbot_api.services.website_rag import website_rag_service
from chatbot_api.services.website_presets import list_website_presets, resolve_website_preset
from chatbot_api.services.domain_detector import classify_domain
from chatbot_api.services.auth_service import auth_service
from chatbot_api.services.rate_limiter import rate_limiter
from chatbot_api.services.session_store import session_store
from chatbot_api.services.tool_runtime import tool_runtime
from chatbot_api.services.webhook_runtime import webhook_runtime

app = FastAPI(title=settings.app_name, version=settings.app_version)
logger = logging.getLogger("chatbot_api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

TOOLS_BY_TENANT: dict[str, list[dict[str, Any]]] = {}
WEBHOOKS_BY_TENANT: dict[str, list[dict[str, str]]] = {}


def _csv_items(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _validate_startup_security() -> None:
    if not settings.strict_startup_validation:
        return

    if settings.cookie_samesite not in {"lax", "strict", "none"}:
        raise RuntimeError("Invalid CHATBOT_COOKIE_SAMESITE; expected one of: lax, strict, none")

    if settings.app_env != "production":
        return

    if not settings.jwt_secret:
        raise RuntimeError("CHATBOT_JWT_SECRET must be configured in production")
    if settings.jwt_secret.strip().lower().startswith("replace-"):
        raise RuntimeError("CHATBOT_JWT_SECRET looks like a placeholder in production")
    if settings.allow_dev_token_auth:
        raise RuntimeError("CHATBOT_ALLOW_DEV_TOKEN_AUTH must be false in production")
    if settings.local_login_enabled:
        raise RuntimeError("CHATBOT_LOCAL_LOGIN_ENABLED must be false in production")
    if not settings.cookie_secure:
        raise RuntimeError("CHATBOT_COOKIE_SECURE must be true in production")


_validate_startup_security()

allowed_origins = _csv_items(settings.cors_allowed_origins)
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

trusted_hosts = _csv_items(settings.trusted_hosts)
if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)


def _error_payload(
    code: str,
    message: str,
    retry_after_ms: int | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id or f"req_{uuid4().hex[:10]}",
        }
    }
    if retry_after_ms is not None:
        payload["error"]["retry_after_ms"] = retry_after_ms
    return payload


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _stream_chat_response(payload: ChatResponse):
    timestamp = datetime.now(timezone.utc).isoformat()
    yield _sse_event(
        "response.started",
        {
            "request_id": payload.request_id,
            "trace_id": payload.trace_id,
            "session_id": payload.session_id,
            "timestamp": timestamp,
        },
    )

    words = payload.message.content.split()
    chunk_size = 8
    for i in range(0, len(words), chunk_size):
        chunk_text = " ".join(words[i : i + chunk_size])
        yield _sse_event(
            "response.delta",
            {
                "request_id": payload.request_id,
                "trace_id": payload.trace_id,
                "session_id": payload.session_id,
                "delta": chunk_text,
            },
        )

    yield _sse_event(
        "response.completed",
        {
            "request_id": payload.request_id,
            "trace_id": payload.trace_id,
            "session_id": payload.session_id,
            "message": payload.message.model_dump(),
            "confidence_score": payload.confidence_score,
            "needs_clarification": payload.needs_clarification,
            "missing_data_fields": payload.missing_data_fields,
            "usage": payload.usage.model_dump(),
            "warnings": payload.warnings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        400: "INVALID_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMIT_EXCEEDED",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, "INTERNAL_ERROR")
    retry_after_ms = None
    if exc.headers and exc.headers.get("X-Retry-After-Ms"):
        try:
            retry_after_ms = int(exc.headers["X-Retry-After-Ms"])
        except ValueError:
            retry_after_ms = None
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code,
            str(exc.detail),
            retry_after_ms=retry_after_ms,
            request_id=getattr(request.state, "request_id", None),
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            "INVALID_REQUEST",
            "Request validation failed",
            request_id=getattr(request.state, "request_id", None),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            "INTERNAL_ERROR",
            "Internal server error",
            request_id=getattr(request.state, "request_id", None),
        ),
    )


@app.middleware("http")
async def logging_and_metrics_middleware(request: Request, call_next):
    request_id = f"req_{uuid4().hex[:10]}"
    request.state.request_id = request_id
    start = time.perf_counter()

    auth = try_parse_auth_header(request.headers.get("Authorization"))
    tenant_id = auth.tenant_id if auth else None
    user_id = auth.user_id if auth else None

    status_code = 500
    try:
        response = await call_next(request)
        status_code = int(response.status_code)
        response.headers["X-Request-Id"] = request_id
        if settings.security_headers_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        return response
    finally:
        latency_ms = (time.perf_counter() - start) * 1000.0
        metrics_store.record(
            path=request.url.path,
            status_code=status_code,
            latency_ms=latency_ms,
            tenant_id=tenant_id,
        )
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 2),
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                }
            )
        )


def _enforce_rate_limit(auth: AuthContext, path: str) -> None:
    allowed, retry_after_ms = rate_limiter.allow(auth.tenant_id, auth.user_id, path)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"X-Retry-After-Ms": str(retry_after_ms)},
        )


def _build_tenant_alerts(tenant_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    requests = int(tenant_metrics.get("requests", 0) or 0)
    errors = int(tenant_metrics.get("errors", 0) or 0)
    avg_latency_ms = float(tenant_metrics.get("avg_latency_ms", 0.0) or 0.0)

    error_rate = (errors / requests * 100.0) if requests > 0 else 0.0
    if error_rate >= settings.alert_error_rate_percent_threshold:
        alerts.append(
            {
                "id": "high_error_rate",
                "severity": "warning",
                "metric": "error_rate_percent",
                "value": round(error_rate, 2),
                "threshold": settings.alert_error_rate_percent_threshold,
                "message": "Tenant error rate is above configured threshold",
            }
        )

    if avg_latency_ms >= settings.alert_avg_latency_ms_threshold:
        alerts.append(
            {
                "id": "high_avg_latency",
                "severity": "warning",
                "metric": "avg_latency_ms",
                "value": round(avg_latency_ms, 2),
                "threshold": settings.alert_avg_latency_ms_threshold,
                "message": "Tenant average latency is above configured threshold",
            }
        )

    return alerts


def _resolve_scope(auth: AuthContext, tenant_id: str | None, user_id: str | None) -> tuple[str, str]:
    resolved_tenant = tenant_id or auth.tenant_id
    resolved_user = user_id or auth.user_id
    enforce_request_scope(auth, resolved_tenant, resolved_user)
    return resolved_tenant, resolved_user


def _enforce_settings_admin(auth: AuthContext, tenant_id: str) -> None:
    if auth.role == "runtime_service":
        return
    if auth.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if auth.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend-assets")


@app.get("/")
def frontend() -> FileResponse:
    if not FRONTEND_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/chatbot")
def chatbot_frontend() -> FileResponse:
    if not FRONTEND_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(FRONTEND_DIR / "chatbot.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, response: Response) -> LoginResponse:
    if not settings.local_login_enabled:
        raise HTTPException(
            status_code=403,
            detail="Local login is disabled. Use your website's existing authentication token.",
        )
    user = auth_service.authenticate(
        tenant_id=request.tenant_id,
        email=request.email,
        password=request.password,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        tenant_id=user["tenant_id"],
        user_id=user["user_id"],
        role=str(user.get("role") or "user"),
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=60 * 60 * 8,
    )
    return LoginResponse(
        tenant_id=user["tenant_id"],
        user_id=user["user_id"],
        role=str(user.get("role") or "user"),
        name=user.get("name"),
        email=user["email"],
    )


@app.post("/v1/auth/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("access_token")
    return {"status": "logged_out"}


@app.get("/metrics")
def prometheus_metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics_store.prometheus_text(), media_type="text/plain; version=0.0.4")


@app.post("/v1/sessions", response_model=SessionResponse)
def create_session(
    request: SessionCreateRequest,
    auth: AuthContext = Depends(require_auth),
) -> SessionResponse:
    tenant_id, user_id = _resolve_scope(auth, request.tenant_id, request.user_id)
    _enforce_rate_limit(auth, "/v1/sessions")
    session_id = f"ses_{uuid4().hex[:12]}"
    session = SessionResponse(
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        channel=request.channel,
    )
    session_store.create(session)
    webhook_runtime.dispatch(
        tenant_id=tenant_id,
        event="session.created",
        payload={
            "session_id": session.session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "channel": request.channel,
        },
    )
    return session


@app.get("/v1/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    auth: AuthContext = Depends(require_auth),
) -> SessionResponse:
    _enforce_rate_limit(auth, "/v1/sessions/{session_id}")
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    enforce_request_scope(auth, session.tenant_id, session.user_id)
    return session


@app.post("/v1/chat")
def chat(
    request: ChatRequest,
    auth: AuthContext = Depends(require_auth),
) -> Any:
    tenant_id, user_id = _resolve_scope(auth, request.tenant_id, request.user_id)
    _enforce_rate_limit(auth, "/v1/chat")
    resolved_session_id = request.session_id
    if not resolved_session_id:
        resolved_session_id = f"ses_{uuid4().hex[:12]}"
        session_store.create(
            SessionResponse(
                session_id=resolved_session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                channel=request.channel,
            )
        )
    session = session_store.get(resolved_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    enforce_request_scope(auth, session.tenant_id, session.user_id)
    request.session_id = resolved_session_id
    request.tenant_id = tenant_id
    request.user_id = user_id
    request.metadata = {**request.metadata, "auth_role": auth.role}
    try:
        response = orchestrator.run(request)
        webhook_runtime.dispatch(
            tenant_id=tenant_id,
            event="chat.completed",
            payload={
                "request_id": response.request_id,
                "trace_id": response.trace_id,
                "session_id": response.session_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "confidence_score": response.confidence_score,
                "needs_clarification": response.needs_clarification,
            },
        )
        if request.stream:
            return StreamingResponse(
                _stream_chat_response(response),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        return response
    except AdminScopeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TenantScopeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AdapterRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v2/research", response_model=dict)
def research(
    request: ResearchRequest,
    raw_request: Request,
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
    tenant_id, user_id = _resolve_scope(auth, request.tenant_id, request.user_id)
    # Feature flag gate for V2 research (tenant override + global fallback)
    if not tenant_settings_service.resolve_v2_enabled(tenant_id):
        raise HTTPException(status_code=403, detail="V2 research is disabled by feature flag")
    _enforce_rate_limit(auth, "/v2/research")
    request.tenant_id = tenant_id
    request.user_id = user_id
    request.user_role = auth.role

    runtime_settings = tenant_settings_service.get_settings(tenant_id)
    if not runtime_settings.website_url:
        inferred_website_url = (request.website_url or "").strip() or None
        if not inferred_website_url:
            origin = (raw_request.headers.get("origin") or "").strip()
            referer = (raw_request.headers.get("referer") or "").strip()
            if origin.startswith("http://") or origin.startswith("https://"):
                inferred_website_url = origin
            elif referer:
                parsed_referer = urlparse(referer)
                if parsed_referer.scheme in {"http", "https"} and parsed_referer.netloc:
                    inferred_website_url = f"{parsed_referer.scheme}://{parsed_referer.netloc}"

        if inferred_website_url:
            classification = classify_domain(
                domain_hint=request.domain_type_hint,
                website_url=inferred_website_url,
                site_metadata=request.site_metadata,
                navigation_context=request.navigation_context,
                product_service_context=request.product_service_context,
                rag_snippets=[],
            )
            preset = resolve_website_preset(
                tenant_id=tenant_id,
                preferred_domain=str(classification.get("primary_domain") or ""),
                preferred_website_url=inferred_website_url,
            )
            inferred_host = (urlparse(inferred_website_url).hostname or "").lower()
            allowed_domains = [inferred_host] if inferred_host else []
            if preset:
                allowed_domains = list(dict.fromkeys([*allowed_domains, *preset.allowed_domains]))

            source_urls: list[str] = [inferred_website_url]
            if preset:
                source_urls = list(dict.fromkeys([*source_urls, *preset.source_urls]))

            tenant_settings_service.update_settings(
                TenantRuntimeSettingsPatch(
                    tenant_id=tenant_id,
                    website_preset_id=preset.preset_id if preset else None,
                    website_url=inferred_website_url,
                    source_urls=source_urls,
                    allowed_domains=allowed_domains,
                    domain_type_hint=str(classification.get("primary_domain") or "other"),
                )
            )

    provider = tenant_settings_service.resolve_v2_provider(tenant_id)
    if provider == "external":
        result = external_research_service.research(request)
        return result.model_dump()
    if provider == "skeleton":
        result = v2_research_service.research(request)
        return result.model_dump()
    raise HTTPException(status_code=500, detail="Invalid CHATBOT_V2_RESEARCH_PROVIDER setting")


@app.get("/v1/admin/settings", response_model=TenantRuntimeSettings)
def get_tenant_runtime_settings(
    tenant_id: str,
    auth: AuthContext = Depends(require_auth),
) -> TenantRuntimeSettings:
    _enforce_rate_limit(auth, "/v1/admin/settings")
    _enforce_settings_admin(auth, tenant_id)
    return tenant_settings_service.get_settings(tenant_id)


@app.patch("/v1/admin/settings", response_model=TenantRuntimeSettings)
def patch_tenant_runtime_settings(
    request: TenantRuntimeSettingsPatch,
    auth: AuthContext = Depends(require_auth),
) -> TenantRuntimeSettings:
    _enforce_rate_limit(auth, "/v1/admin/settings")
    _enforce_settings_admin(auth, request.tenant_id)
    return tenant_settings_service.update_settings(request)


@app.post("/v1/admin/website/index", response_model=WebsiteIndexResponse)
def index_website_content(
    request: WebsiteIndexRequest,
    auth: AuthContext = Depends(require_auth),
) -> WebsiteIndexResponse:
    _enforce_rate_limit(auth, "/v1/admin/website/index")
    _enforce_settings_admin(auth, request.tenant_id)
    stats = website_rag_service.ingest_site(
        tenant_id=request.tenant_id,
        website_url=request.website_url,
        allowed_domains=request.allowed_domains,
        max_pages=request.max_pages,
        max_depth=request.max_depth,
    )
    return WebsiteIndexResponse(tenant_id=request.tenant_id, **stats)


@app.get("/v1/admin/website/index", response_model=WebsiteIndexResponse)
def get_website_index_stats(
    tenant_id: str,
    auth: AuthContext = Depends(require_auth),
) -> WebsiteIndexResponse:
    _enforce_rate_limit(auth, "/v1/admin/website/index")
    _enforce_settings_admin(auth, tenant_id)
    stats = website_rag_service.stats(tenant_id)
    return WebsiteIndexResponse(tenant_id=tenant_id, **stats)


@app.post("/v1/tools/register")
def register_tools(
    request: ToolsRegisterRequest,
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
    _enforce_rate_limit(auth, "/v1/tools/register")
    if auth.tenant_id != request.tenant_id and auth.role != "runtime_service":
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    tool_runtime.register(request.tenant_id, request.tools)
    TOOLS_BY_TENANT[request.tenant_id] = [tool.model_dump() for tool in request.tools]
    return {"tenant_id": request.tenant_id, "registered_count": len(request.tools)}


@app.get("/v1/tools")
def list_tools(
    tenant_id: str,
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
    _enforce_rate_limit(auth, "/v1/tools")
    if auth.tenant_id != tenant_id and auth.role != "runtime_service":
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    tools = [tool.model_dump() for tool in tool_runtime.list_tools(tenant_id)]
    return {"tenant_id": tenant_id, "tools": tools}


@app.post("/v1/tools/invoke")
def invoke_tool(
    request: ToolInvokeRequest,
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
    _enforce_rate_limit(auth, "/v1/tools/invoke")
    tenant_id, user_id = _resolve_scope(auth, request.tenant_id, request.user_id)
    result = tool_runtime.invoke(
        tenant_id=tenant_id,
        user_id=user_id,
        role=auth.role,
        tool_name=request.tool_name,
        params=request.params,
    )
    webhook_runtime.dispatch(
        tenant_id=tenant_id,
        event="tool.invoked",
        payload={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "tool_name": request.tool_name,
            "status": result.status,
            "duration_ms": result.duration_ms,
        },
    )
    return result.model_dump()


@app.post("/v1/webhooks")
def register_webhook(
    request: WebhookRegistration,
    auth: AuthContext = Depends(require_auth),
) -> dict[str, str]:
    _enforce_rate_limit(auth, "/v1/webhooks")
    if auth.tenant_id != request.tenant_id and auth.role != "runtime_service":
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    webhook_runtime.register(
        tenant_id=request.tenant_id,
        event=request.event,
        callback_url=request.callback_url,
        secret=request.secret,
    )
    existing = WEBHOOKS_BY_TENANT.setdefault(request.tenant_id, [])
    existing.append(request.model_dump())
    return {"status": "registered", "event": request.event}


@app.get("/v1/webhooks/dead-letters")
def webhook_dead_letters(
    tenant_id: str,
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
    _enforce_rate_limit(auth, "/v1/webhooks/dead-letters")
    if auth.tenant_id != tenant_id and auth.role != "runtime_service":
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    return {"tenant_id": tenant_id, "dead_letters": webhook_runtime.list_dead_letters(tenant_id)}


@app.get("/v1/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "streaming": True,
        "tools": True,
        "citations": True,
        "memory": False,
        "multimodal": False,
        "grounding_mode": "client_data_first",
        "adapter_mode": adapter_mode(),
        "tool_runtime": True,
        "webhook_runtime": True,
        "external_research": settings.external_research_enabled,
        "v2_enabled": settings.enable_v2,
        "v2_research_provider": settings.v2_research_provider,
    }


@app.get("/v1/website/presets", response_model=list[WebsitePreset])
def website_presets() -> list[WebsitePreset]:
    return list_website_presets()


@app.post("/v1/domain/classify", response_model=DomainClassifyResponse)
def classify_website_domain(request: DomainClassifyRequest) -> DomainClassifyResponse:
    result = classify_domain(
        domain_hint=request.domain_hint,
        website_url=request.website_url,
        site_metadata=request.site_metadata,
        navigation_context=request.navigation_context,
        product_service_context=request.product_service_context,
        rag_snippets=request.rag_snippets,
    )
    return DomainClassifyResponse(**result)


@app.post("/v1/admin/website/integrate", response_model=WebsiteAutoIntegrateResponse)
def auto_integrate_website(
    request: WebsiteAutoIntegrateRequest,
    auth: AuthContext = Depends(require_auth),
) -> WebsiteAutoIntegrateResponse:
    _enforce_rate_limit(auth, "/v1/admin/website/integrate")
    _enforce_settings_admin(auth, request.tenant_id)

    classification = classify_domain(
        domain_hint=None,
        website_url=request.website_url,
        site_metadata=None,
        navigation_context=None,
        product_service_context=None,
        rag_snippets=[],
    )

    preset = resolve_website_preset(
        tenant_id=request.tenant_id,
        preferred_domain=str(classification.get("primary_domain") or ""),
        preferred_website_url=request.website_url,
    )

    host = (urlparse(request.website_url).hostname or "").lower()
    allowed_domains = [host] if host else []
    if preset:
        allowed_domains = list(dict.fromkeys([*allowed_domains, *preset.allowed_domains]))

    source_urls = [request.website_url]
    if preset and preset.website_url and host and host in {item.lower() for item in preset.allowed_domains}:
        source_urls = preset.source_urls or [request.website_url]

    stats = website_rag_service.ingest_site(
        tenant_id=request.tenant_id,
        website_url=request.website_url,
        allowed_domains=allowed_domains,
        max_pages=request.max_pages,
        max_depth=request.max_depth,
    )

    tenant_settings_service.update_settings(
        TenantRuntimeSettingsPatch(
            tenant_id=request.tenant_id,
            v2_enabled=True,
            website_preset_id=preset.preset_id if preset else None,
            website_url=request.website_url,
            source_urls=source_urls,
            allowed_domains=allowed_domains,
            domain_type_hint=str(classification.get("primary_domain") or "other"),
        )
    )

    return WebsiteAutoIntegrateResponse(
        tenant_id=request.tenant_id,
        website_url=request.website_url,
        primary_domain=str(classification.get("primary_domain") or "other"),
        secondary_domain=(str(classification.get("secondary_domain")) if classification.get("secondary_domain") else None),
        preset_id=preset.preset_id if preset else None,
        pages_indexed=stats.get("pages_indexed", 0),
        chunks_indexed=stats.get("chunks_indexed", 0),
    )


@app.get("/v1/usage")
def usage(auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    _enforce_rate_limit(auth, "/v1/usage")
    session_count = session_store.count_by_tenant(auth.tenant_id)
    return {
        "tenant_id": auth.tenant_id,
        "sessions": session_count,
        "messages": 0,
        "model": settings.default_model,
        "adapter_mode": adapter_mode(),
    }


@app.get("/v1/metrics")
def metrics(auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    _enforce_rate_limit(auth, "/v1/metrics")
    return metrics_store.snapshot(tenant_id=auth.tenant_id)


@app.get("/v1/alerts")
def alerts(auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    _enforce_rate_limit(auth, "/v1/alerts")
    snapshot = metrics_store.snapshot(tenant_id=auth.tenant_id)
    tenant_metrics = snapshot.get("tenant", {})
    return {
        "tenant_id": auth.tenant_id,
        "alerts": _build_tenant_alerts(tenant_metrics),
        "thresholds": {
            "error_rate_percent": settings.alert_error_rate_percent_threshold,
            "avg_latency_ms": settings.alert_avg_latency_ms_threshold,
        },
    }
