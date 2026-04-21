# Documentation Changelog

All notable changes to the documentation are tracked in this file.

## [Unreleased]

- Added existing-site JWT integration support via claim mapping (`CHATBOT_JWT_CLAIM_*`) and issuer/audience validation config.
- Added optional local-login disable switch (`CHATBOT_LOCAL_LOGIN_ENABLED`) for production integration mode.
- Made `/v1/chat` scope fields optional so tenant/user can be derived directly from authentication context.
- Added tenant domain policy guardrails so chatbot answers only domain-relevant questions per website/tenant.
- Added tenant profile support in seed data (`chatbot_tenant_profiles`) with finance/event domain mapping examples.
- Added credential-based login/logout endpoints with HTTP-only cookie auth (`/v1/auth/login`, `/v1/auth/logout`).
- Added automatic session creation in `/v1/chat` when `session_id` is omitted.
- Updated frontend to use login credentials instead of token/session bootstrap flow.
- Added `verbose` flag support to `/v1/chat` for explicit explanation mode (default remains concise).
- Added `verbose` flag to `POST /v2/research` for explicit detailed explanation mode.
- Updated V2 research response style to be concise and action-first, with no citations in output by default.
- Added conditional explanation field in V2 research responses only when users explicitly ask for details.
- Added V2 research endpoint (`POST /v2/research`) that combines user-specific context with trusted external source analysis.
- Added OpenAPI snapshot contract test (`tests/test_openapi_contract.py`) and contract drift check script (`scripts/check_openapi_contract.py`).
- Added regression suite (`tests/test_regression_suite.py`) for typo robustness and admin-scope policy checks.
- Added `docs/v1-release-runbook.md` with exact V1 release commands.
- Switched default auth posture to JWT-first (`CHATBOT_ALLOW_DEV_TOKEN_AUTH=false` by default).
- Added OpenAPI export helper script (`scripts/export_openapi.py`) and contract-freeze documentation.
- Added Prometheus-compatible `/metrics` endpoint.
- Added `/v1/alerts` endpoint with configurable tenant alert thresholds for error-rate and average latency.
- Added structured request logging middleware with `request_id`, `tenant_id`, `user_id`, status, and latency.
- Added basic in-memory metrics store and `/v1/metrics` endpoint with tenant counters.
- Added deployment assets: `Dockerfile`, `docker-compose.yml`, `.env.example`, and `.dockerignore`.
- Added SQL seed script `scripts/seed_test_db.py` with tenant-isolated demo data.
- Enforced SQL tenant isolation using `users.tenant_id` or `chatbot_tenant_users` mapping with explicit 403 on cross-tenant access.
- Added tool runtime endpoints (`/v1/tools`, `/v1/tools/invoke`) with role-based permissions and timeout enforcement.
- Added webhook runtime delivery worker with HMAC signatures, retries, and dead-letter queue endpoint (`/v1/webhooks/dead-letters`).
- Added per-tenant/per-user in-memory rate limiting with explicit 429 error envelope and `retry_after_ms`.
- Implemented SSE streaming for `/v1/chat` with `response.started`, `response.delta`, and `response.completed` events.
- Added durable session storage with SQL-backed `chatbot_sessions` table and in-memory fallback when DB is not configured.
- Added `docs/v1-go-live-checklist.md` with must-have production blockers and implementation status.
- Implemented JWT authentication support with configurable secret/algorithm.
- Added unified API error envelope for HTTP, validation, and unhandled errors.
- Enforced admin-only platform query access with explicit 403 responses for non-admin users.
- Standardized model/auth examples across docs (`qwen2.5-7b-instruct`, `$APP_TOKEN`) for consistency.
- Updated all existing docs for open-source-only deployment mode (no paid external model API keys).
- Replaced API key language with JWT/service-token authentication guidance where applicable.
- Added self-hosted model operations and release checks (model manifest, fallback, upgrade validation).
- Added `docs/personalization-test-cases.md` with QA/UAT scenarios for account-scoped responses and typo/noisy-input handling.
- Updated `docs/README.md` reading order to include `docs/personalization-test-cases.md`.
- Updated all docs to include user-specific and product-specific grounding requirements.
- Added noisy-input (typo-tolerant) behavior rules and acceptance criteria.
- Added account-scoped reliability checks in `docs/operations-runbook.md`.
- Updated `docs/api-reference.md` with grounding behavior and response metadata guidance.
- Added `docs/product-rules.md` with end-product rules, release gates, and definition of done.
- Updated `docs/README.md` reading order and ownership to include `product-rules.md`.
- Added split documentation set:
  - `docs/architecture.md`
  - `docs/api-reference.md`
  - `docs/operations-runbook.md`
- Added docs index and ownership guide in `docs/README.md`.
- Added split-doc pointer in `chatbot-api-documentation.md`.

## [v1.0.0-docs] - 2026-04-17

- Created initial master documentation in `chatbot-api-documentation.md`.
- Defined architecture, API surface, operations standards, security, compliance, and SLO baselines.

---

## Changelog Rules

- Keep entries concise and grouped by release/version.
- Use `Unreleased` for ongoing changes and move them into a version section when finalized.
- Reference affected files directly for fast navigation.
