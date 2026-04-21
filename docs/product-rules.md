# End Product Rules

These rules define what "production-ready and easy to integrate" means for the Universal Chatbot API.

## 1) Product Goal Rules

- The platform must be domain-agnostic and support integrations for any application category without core code rewrites.
- The platform must provide user-specific responses by grounding outputs in tenant config, user context, and allowed tools.
- The platform must expose stable, versioned API contracts with backward compatibility within `v1`.
- The platform must run on open-source/self-hosted AI components without requiring paid external model API keys.

## 2) Functional Rules

- The API must support `chat`, `sessions`, `tools`, `webhooks`, `capabilities`, and `usage` endpoints.
- The API must support both non-streaming and streaming (SSE) response modes.
- Tool calling must be policy-controlled, schema-validated, timeout-bounded, and auditable.
- Session memory must include short-term context and configurable summarization for long threads.
- The response payload must include `request_id`, `trace_id`, `confidence_score`, and optional `citations`.
- The API must accept noisy text input (typos, mixed grammar, shorthand) and still resolve intent reliably.
- The API must return account-specific answers for authenticated users and never default to generic advice when account context is available.

## 2.1) Personalization and Noisy Input Acceptance Rules

- Every `POST /v1/chat` request must be identity-bound to authenticated `tenant_id` and `user_id`.
- User-specific answers must be grounded in client application data via approved tools/adapters.
- If required account data is missing, stale, or unauthorized, the assistant must ask a clarifying question instead of guessing.
- The orchestrator must run input normalization before retrieval/tool routing (spelling tolerance, shorthand expansion, intent cleanup).
- The response must include actionable output where applicable (overview, what is working, what to improve, and suggested next steps).
- Cross-user data leakage is a hard failure condition.

## 3) Integration Rules

- New application integrations must use a standard adapter contract (`get_user_context`, `get_domain_entities`, `run_action`, `policy_checks`).
- Integration onboarding must be possible in 4 steps: create tenant, register tools/adapters, configure prompt/policy, call `/v1/chat`.
- A capability discovery endpoint (`/v1/capabilities`) must expose enabled features for each tenant.
- Official JS/TS SDK must include typed models, retry support, SSE helper, and idempotency helper.

## 4) Security and Isolation Rules

- Every request and record must be tenant-scoped; cross-tenant data access must be blocked by design.
- Auth must support JWT/service-token-based user context and internal service authentication.
- Secrets must be stored in a secure vault, never hardcoded in code or docs.
- Data must be encrypted in transit (TLS 1.2+) and at rest.
- Webhooks must use signature verification (HMAC or equivalent).

## 5) Reliability and Performance Rules

- Services must be stateless where possible and horizontally scalable.
- Self-hosted model runtimes and tool calls must have timeout, retry, and circuit-breaker protection.
- Async flows must use queue workers with retry and dead-letter handling.
- Degradation paths must exist for model/tool failures (fallback model or safe response mode).
- Open-source model fallback order must be configured and tested (primary, secondary, safe-mode responder).
- Baseline SLOs:
  - Availability: `99.9%`
  - Non-stream first response: `p95 < 2.5s`
  - Stream start: `p95 < 700ms`
  - Error rate (excluding 4xx): `< 1%`

## 6) Safety and Policy Rules

- Input and output moderation checks must run on every chat request.
- The assistant must not fabricate domain facts when required context is missing; it must ask clarifying questions.
- Tool access must be allowlisted per tenant and enforce parameter validation.
- Prompt injection defenses must be implemented for model/tool boundaries.
- Policy packs must be configurable per tenant/domain without code changes.

## 7) Observability and Audit Rules

- Structured logs must include `tenant_id`, `user_id`, `session_id`, `request_id`, and `trace_id`.
- End-to-end traces must be available for orchestrator, model calls, and tool calls.
- Metrics must track latency, errors, tool success, fallback rate, token usage, and cost.
- Audit logs must record policy decisions, tool calls, and response generation metadata.

## 8) Data Governance Rules

- Retention controls must be configurable per tenant.
- User data export and deletion endpoints must be available.
- PII masking/redaction must be configurable before model invocation.
- Region/data residency requirements must be enforceable for enterprise tenants.

## 9) Developer Experience Rules

- The API contract must be published as OpenAPI and validated in CI.
- Error responses must follow a consistent envelope with machine-readable `code` values.
- Docs must include quickstart examples, streaming examples, and end-to-end integration samples.
- Breaking changes must only occur with a major version bump.

## 10) Release and Quality Gate Rules

Before production release, all of the following must pass:

- Unit tests, integration tests, and API contract tests.
- Tenant isolation test suite.
- Load/performance test against target concurrency.
- Security checks (dependency scan, secret scan, baseline penetration findings triaged).
- Regression evaluation set for factuality, safety, and personalization relevance.
- Open-source model upgrade test pass (quality, latency, and memory usage) before promotion.

## 11) Definition of Done (Launch)

The end product is ready for launch only when:

- All core endpoints are implemented and documented.
- At least 2 different domain adapters are live (for proof of domain-agnostic architecture).
- SDK and Postman collection are published and verified.
- SLO dashboards and alerting are active.
- Runbooks for incident handling and rollback are available.
- Pilot integration can go from tenant setup and token configuration to first successful response within one business day.
- Noisy-input tests (typo-heavy prompts) pass with acceptable intent resolution and grounded responses.
