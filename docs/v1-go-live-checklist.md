# V1 Go-Live Checklist

## Scope

This checklist tracks minimum requirements for V1 production readiness.

## Must-Have (Blockers)

- [x] **M1 - Real auth support**: signed JWT verification with expiry-aware decoding.
- [x] **M2 - Role and scope enforcement**: deny admin-scope queries for non-admin users.
- [x] **M3 - Standard error contract**: return unified `error` envelope for HTTP/validation/server failures.
- [x] **M4 - Session durability**: persist sessions in DB or distributed cache.
- [x] **M5 - Streaming implementation**: SSE streaming for chat responses.
- [x] **M6 - Tool execution runtime**: actual tool invoke path with permissions and timeouts.
- [x] **M7 - Webhook delivery runtime**: signed webhook dispatch with retry/dead-letter behavior.
- [x] **M8 - Tenant isolation in SQL**: tenant-partitioned queries and database-level isolation checks.
- [x] **M9 - Rate limiting**: endpoint-level per-tenant and per-user limits.

## Important (V1 Quality)

- [x] Structured logging (`request_id`, `tenant_id`, `user_id`, latency).
- [x] Basic metrics and alert hooks (error/latency/sql-failure counters).
- [x] OpenAPI contract checks in CI.
- [x] Prompt and policy regression suite (typo robustness + personalization).

## Current Notes

- Chat persistence is intentionally disabled by product requirement.
- SQL mode uses strict numeric `users.id` resolution.
- Admin-only platform insight access is enforced.
