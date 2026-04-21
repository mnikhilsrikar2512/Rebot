# Universal Chatbot API Platform Documentation (v1.0 Draft)

> This master document has been split into maintainable docs:
>
> - `docs/product-rules.md`
> - `docs/architecture.md`
> - `docs/api-reference.md`
> - `docs/operations-runbook.md`
> - `docs/CHANGELOG.md`
> - `docs/personalization-test-cases.md`

> Product requirement focus: account-scoped, user-specific responses grounded in client application data, including robust handling of typo/noisy input.
>
> Deployment requirement focus: open-source and self-hosted only, with no paid external model API keys.

## 1) Overview

The Universal Chatbot API is a domain-agnostic conversational platform that integrates with any application (finance, education, business, event management, CRM, ERP, and more).

It delivers user-specific responses using tenant configuration, user context, and optional tool calls.

It is designed for production from day one: secure multi-tenancy, observability, reliability controls, and backward-compatible versioning.

### Primary Goals

- Easy to integrate into any app within hours.
- Personalized responses without hardcoding domain logic in the core API.
- Provider-agnostic model gateway with failover.
- Enterprise-ready security, governance, and auditability.

## 2) Core Concepts

- **Tenant**: A customer/workspace using the platform.
- **User**: End user within a tenant.
- **Session**: Conversation container for context continuity.
- **Message**: Unit of user/assistant/tool communication.
- **Tool**: External function/API callable by the assistant.
- **Adapter**: Domain/application connector implementing the standard contract.
- **Policy**: Rules controlling behavior, safety, and tool access.
- **Prompt Pack**: Versioned instructions for assistant behavior.
- **Trace**: End-to-end execution record for debugging/audit.

## 3) High-Level Architecture

- **API Gateway**: Authentication, rate limits, request validation.
- **Chat Orchestrator**: Builds prompt, calls model, handles tool execution loop.
- **Context Service**: Pulls user/app context via adapters.
- **Tool Registry**: Tenant-scoped tool definitions and permissions.
- **Policy Engine**: Input/output safety checks and rule enforcement.
- **Memory Service**: Session history and summarization.
- **Model Gateway**: Routes to self-hosted model runtimes with fallback.
- **Storage**: Postgres (source of truth), Redis (cache/session hot path), object storage (attachments).
- **Queue Workers**: Async tasks (webhooks, long tool calls, background indexing).
- **Observability Stack**: Logs, metrics, traces, alerts.

## 4) API Design Principles

- Versioned endpoints (`/v1/...`) and no breaking changes inside a major version.
- JSON-first contracts with explicit schemas.
- Idempotent write operations using `Idempotency-Key`.
- Streaming and non-streaming support.
- Deterministic error envelope.
- Correlation via `request_id` and `trace_id` in all responses.

## 5) Authentication and Authorization

- **Server-to-server**: signed service token/JWT (`Authorization: Bearer <token>`).
- **User-context calls**: JWT support (`sub`, `tenant_id`, roles).
- **RBAC** roles: `tenant_admin`, `developer`, `analyst`, `runtime_service`.
- **Least privilege**: Tool execution allowed only when explicitly granted by policy.

## 6) Multi-Tenant Data Isolation

- Every record includes `tenant_id`.
- DB row-level protections and query guards.
- Cache keys namespaced by tenant.
- Strict prohibition on cross-tenant retrieval.
- Isolation tests required in CI.

## 7) Core Endpoints (v1)

### `POST /v1/chat`

Main entrypoint for conversational responses.

Request example:

```json
{
  "tenant_id": "tnt_123",
  "user_id": "usr_456",
  "session_id": "ses_789",
  "message": {
    "role": "user",
    "content": "Can I reduce my monthly expenses?"
  },
  "channel": "web",
  "stream": true,
  "context": {
    "locale": "en-US",
    "timezone": "Asia/Kolkata"
  },
  "metadata": {
    "app_version": "1.2.0"
  }
}
```

Response example (non-stream):

```json
{
  "request_id": "req_abc",
  "trace_id": "trc_xyz",
  "session_id": "ses_789",
  "message": {
    "role": "assistant",
    "content": "Yes. Based on your recent spending, you can start by reducing dining and subscriptions by 10-15%.",
    "citations": [
      { "source_type": "tool", "source_id": "tool.spending_summary", "timestamp": "2026-04-17T10:20:00Z" }
    ]
  },
  "confidence_score": 0.87,
  "needs_clarification": false,
  "missing_data_fields": [],
  "usage": {
    "input_tokens": 912,
    "output_tokens": 134,
    "model": "qwen2.5-7b-instruct"
  },
  "warnings": []
}
```

### `POST /v1/sessions`

Creates/resumes a session and returns `session_id`, TTL, and memory config.

### `GET /v1/sessions/{session_id}`

Fetch session metadata and status.

### `POST /v1/tools/register`

Register tenant-scoped tools.

```json
{
  "tenant_id": "tnt_123",
  "tools": [
    {
      "name": "get_user_profile",
      "description": "Fetch profile by user id",
      "input_schema": {
        "type": "object",
        "properties": {
          "user_id": { "type": "string" }
        },
        "required": ["user_id"]
      },
      "timeout_ms": 3000
    }
  ]
}
```

### `POST /v1/webhooks`

Register event callback endpoint and secret.

### `GET /v1/capabilities`

Discover enabled tenant features (streaming, tools, citations, memory, multimodal flags).

### `GET /v1/usage`

Usage and billing metrics by date/tenant/model.

## 8) Streaming Protocol (SSE)

- Content type: `text/event-stream`.
- Event types:
  - `response.started`
  - `response.delta`
  - `tool.called`
  - `tool.completed`
  - `response.completed`
  - `response.failed`
- Each event includes `request_id`, `trace_id`, and `timestamp`.

## 9) Universal Adapter Contract

Every domain/app integration implements this standard contract:

- `get_user_context(user_id, tenant_id)` returns normalized user profile/preferences.
- `get_domain_entities(query, user_id, tenant_id)` returns relevant business objects (courses, invoices, events, tickets, and so on).
- `run_action(action_name, params, user_id, tenant_id)` executes allowed domain action.
- `policy_checks(input, candidate_output, tenant_id)` optionally applies custom policy gating.

This keeps the core chatbot generic while allowing deep personalization.

## 10) Prompt Orchestration

Final prompt is assembled from:

- Base system instructions.
- Tenant prompt pack (brand voice, behavior).
- Domain pack (optional constraints/tool hints).
- User context summary.
- Recent session memory (window + summarized older context).
- Current user message.

### Prompt Versioning

- `prompt_pack_id`, `version`, `checksum`.
- Supports canary rollout and rollback.

## 11) Memory Strategy

- Short-term memory: recent turns (configurable N/token window).
- Summarized memory: condensed history for long sessions.
- Long-term preferences: optional key-value profile store.
- Retention: policy-driven per tenant with delete/export support.

## 12) Policy and Safety

- Input checks: injection patterns, unsafe content, malformed payloads.
- Output checks: policy violations, hallucination risk, restricted advice classes.
- Tool policy: allowlist plus parameter validation.
- Optional domain guardrails (finance/health/legal and others).
- If uncertain, ask for clarification rather than fabricating facts.

## 13) Error Handling

Standard error envelope:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests for tenant tnt_123",
    "request_id": "req_abc",
    "retry_after_ms": 1200
  }
}
```

Common error codes:

- `INVALID_REQUEST`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `CONFLICT`
- `RATE_LIMIT_EXCEEDED`
- `UPSTREAM_MODEL_TIMEOUT`
- `TOOL_EXECUTION_FAILED`
- `POLICY_BLOCKED`
- `INTERNAL_ERROR`

## 14) Observability Standards

- Logs: JSON structured with `tenant_id`, `user_id`, `session_id`, `request_id`, `trace_id`.
- Metrics:
  - request count, error rate, p50/p95/p99 latency
  - tool success rate
  - token consumption and cost
  - fallback activation rate
- Traces: orchestrator -> model call -> tool calls -> response validation.
- Alerts:
  - latency SLO breach
  - model runtime outage/fallback surge
  - cost spike anomaly
  - webhook failure rate

## 15) Reliability and Scalability

- Stateless API instances behind load balancer.
- Redis for hot context/cache and Postgres as durable store.
- Queue for async tasks and retries.
- Circuit breaker per model runtime/tool endpoint.
- Graceful degradation:
  - fallback model
  - no-tool safe response path
  - queued response for long-running flows

## 16) Security Requirements

- TLS 1.2+ in transit.
- Encryption at rest (DB/object storage).
- Secrets in a vault (avoid plain production env exposure).
- Service token/JWT key material hashing, rotation, and expiry policy.
- HMAC verification for incoming webhooks.
- Immutable/append-only audit logs.
- Periodic vulnerability scans and dependency audits.

## 17) Compliance and Data Governance

- Data retention policy per tenant.
- DSAR endpoints for export/delete user data.
- Region-aware data residency controls.
- PII masking/redaction before model calls when configured.
- Explicit data processing disclosure and consent controls.

## 18) Easy Integration Guide

1. Create tenant and configure auth token issuance.
2. Register tools/adapters (optional but recommended).
3. Configure prompt pack and policies.
4. Create session.
5. Send first chat request (streaming or non-streaming).
6. Subscribe to webhooks for async events.
7. Use `request_id` and `trace_id` for support/debug.

Minimal curl example:

```bash
curl -X POST https://api.example.com/v1/chat \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 4f3b8f29-6c5b-4a6a-9f7d-a061e5d11f0c" \
  -d '{
    "tenant_id":"tnt_123",
    "user_id":"usr_456",
    "session_id":"ses_789",
    "message":{"role":"user","content":"Help me plan this week"},
    "stream":false
  }'
```

## 19) SDK Requirements (v1)

- JS/TS SDK first.
- Features:
  - typed request/response models
  - automatic retries (safe status codes only)
  - SSE helper
  - idempotency helper
  - middleware hooks for logging
- Include 3 sample apps:
  - web app integration
  - backend service integration
  - tool registration plus invocation flow

## 20) Testing and Quality Gates

- Unit tests: orchestrator, policy checks, adapters.
- Contract tests: OpenAPI conformance.
- Integration tests: model + tool-call loop.
- Isolation tests: cross-tenant leakage prevention.
- Load tests: target RPS and p95 latency.
- Regression eval sets:
  - factuality
  - safety
  - personalization relevance
  - response style consistency

## 21) CI/CD and Release

- Branch protections and required checks.
- Build, test, and security scan on every PR.
- Deploy via blue/green or canary.
- Backward-compatible DB migrations.
- Release artifacts:
  - OpenAPI spec
  - SDK version
  - changelog with migration notes

## 22) Recommended SLOs

- Availability: `99.9%`.
- Latency: `p95 < 2.5s` non-stream first response, `p95 < 700ms` stream start.
- Error rate: `< 1%` (excluding 4xx).
- Webhook delivery success: `> 99%` within retry policy.

## 23) v1 Non-Goals

- Native multimodal generation (text-only initially).
- Public marketplace for adapters.
- Advanced A/B experimentation UI.
- No-code workflow builder.

## 24) Project Folder Structure (Reference)

```text
/chatbot-platform
  /apps
    /api-gateway
    /orchestrator
    /worker
  /packages
    /sdk-js
    /openapi
    /policy-engine
    /prompt-manager
    /tool-runtime
  /infra
    /terraform
    /k8s
  /docs
    /architecture
    /api
    /runbooks
```

## 25) Implementation Milestones

- `M1`: API contracts + auth + sessions + basic chat.
- `M2`: tool calling + adapter contract + streaming.
- `M3`: policy engine + observability + rate limits.
- `M4`: hardening (security/reliability) + SDK + docs.
- `M5`: pilot rollout + SLO monitoring + feedback loop.
