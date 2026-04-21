# Universal Chatbot API - Operations Runbook

Operating mode: self-hosted open-source models only (no paid external model APIs).

## Observability Standards

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

## Reliability and Scalability

- Stateless API instances behind load balancer.
- Redis for hot context/cache and Postgres as durable store.
- Queue for async tasks and retries.
- Circuit breaker per model runtime/tool endpoint.
- Capacity controls for local model serving: GPU memory limits, batch sizing, and request queue limits.
- Graceful degradation:
  - fallback open-source model
  - no-tool safe response path
  - queued response for long-running flows

## Open-Source Model Operations

- Maintain approved model list with version pinning.
- Keep rollback-ready previous model artifacts for rapid recovery.
- Track model load time, VRAM usage, and tokens/second as core health metrics.
- Run regression suite before promoting any model upgrade.

## Security Requirements

- TLS 1.2+ in transit.
- Encryption at rest (DB/object storage).
- Secrets in a vault (avoid plain production env exposure).
- Service token/JWT key material hashing, rotation, and expiry policy.
- Internal token signing key rotation and expiry enforcement.
- HMAC verification for incoming webhooks.
- Immutable/append-only audit logs.
- Periodic vulnerability scans and dependency audits.

## Compliance and Data Governance

- Data retention policy per tenant.
- DSAR endpoints for export/delete user data.
- Region-aware data residency controls.
- PII masking/redaction before model calls when configured.
- Explicit data processing disclosure and consent controls.

## Testing and Quality Gates

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
  - noisy-input robustness (typos, shorthand, grammar variance)
  - account-scoping correctness (no cross-user leakage)

## Personalization Reliability Checks

- Validate identity binding on every chat request (`tenant_id` + `user_id`).
- Run synthetic tests where users ask the same question with spelling errors and verify equivalent intent routing.
- Verify account-specific replies are grounded in current client data and include missing-field prompts when needed.
- Add alerting for unusual spikes in `needs_clarification` and `missing_data_fields` to catch adapter failures.

## CI/CD and Release

- Branch protections and required checks.
- Build, test, and security scan on every PR.
- Deploy via blue/green or canary.
- Backward-compatible DB migrations.
- Release artifacts:
  - OpenAPI spec
  - SDK version
  - model manifest (approved OSS model versions)
  - changelog with migration notes

## V2 Rollout Controls

- `CHATBOT_ENABLE_V2`: master gate for all V2 behavior.
- `CHATBOT_V2_RESEARCH_PROVIDER`: provider switch on same endpoint (`skeleton` or `external`).
- Recommended rollout:
  - Stage 1: `CHATBOT_ENABLE_V2=true`, `CHATBOT_V2_RESEARCH_PROVIDER=skeleton`
  - Stage 2: switch to `CHATBOT_V2_RESEARCH_PROVIDER=external`
  - Rollback: set provider back to `skeleton` or disable with `CHATBOT_ENABLE_V2=false`
- Track V2-specific metrics during rollout:
  - request count and error rate for `/v2/research`
  - provider split (`skeleton` vs `external`)
  - external-source fetch failure rate

## Recommended SLOs

- Availability: `99.9%`.
- Latency: `p95 < 2.5s` non-stream first response, `p95 < 700ms` stream start.
- Error rate: `< 1%` (excluding 4xx).
- Webhook delivery success: `> 99%` within retry policy.

## v1 Non-Goals

- Native multimodal generation (text-only initially).
- Public marketplace for adapters.
- Advanced A/B experimentation UI.
- No-code workflow builder.

## Implementation Milestones

- `M1`: API contracts + auth + sessions + basic chat.
- `M2`: tool calling + adapter contract + streaming.
- `M3`: policy engine + observability + rate limits.
- `M4`: hardening (security/reliability) + SDK + docs.
- `M5`: pilot rollout + SLO monitoring + feedback loop.
