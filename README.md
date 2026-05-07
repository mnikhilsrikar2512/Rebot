# Universal Chatbot API

A production-oriented, tenant-aware chatbot backend built with FastAPI. The service supports JWT authentication, account-scoped responses, SQL Server integration, configurable runtime behavior per tenant, and a browser-based tester for fast validation.

## Core Capabilities

- Multi-tenant chat API with strict tenant/user scope enforcement
- JWT-based authentication with configurable claim mapping
- SQL Server adapter with mock fallback support for local development
- V1 chat and V2 research flows with feature flags and provider switching
- Per-tenant runtime tuning (response style, recommendation depth, V2 overrides)
- Domain-aware guardrails and classification (12-domain taxonomy) for scoped responses
- Website preset automation (predefined domains/sources) with tenant-level auto-resolution
- Role-aware policy enforcement (admin vs user) from JWT auth context
- Built-in rate limiting, metrics, and request traceability (`X-Request-Id`)

## API Surface

- `POST /v1/auth/login` and `POST /v1/auth/logout` (local/dev auth mode)
- `POST /v1/sessions`, `GET /v1/sessions/{session_id}`
- `POST /v1/chat`
- `POST /v2/research`
- `GET /v1/capabilities`
- `GET /metrics`, `GET /v1/metrics`, `GET /v1/alerts`
- `GET /v1/admin/settings`, `PATCH /v1/admin/settings` (tenant runtime tuning)
- `POST /v1/admin/website/index`, `GET /v1/admin/website/index`
- `POST /v1/admin/website/integrate` (instant website integration + domain auto-config)
- `GET /v1/website/presets` (predefined website/domain presets)
- `POST /v1/domain/classify` (domain detection + behavior capabilities)

## Repository Layout

```text
src/chatbot_api/   API, auth, adapters, services, runtime policies
frontend/          Browser tester UI (V1 + V2 + admin runtime tuning)
scripts/           DB seed, OpenAPI export/check, smoke scripts
tests/             API, regression, and contract tests
docs/              Product, operations, release, and service-model docs
openapi/           Versioned OpenAPI snapshots
```

## Quick Start (Local)

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Prepare environment:

```bash
cp .env.example .env
```

4. Start the API:

```bash
PYTHONPATH=src uvicorn chatbot_api.main:app --reload
```

5. Open:

- API docs: `http://127.0.0.1:8000/docs`
- API root status: `http://127.0.0.1:8000/`
- Frontend chatbot: `http://127.0.0.1:8000/chatbot`

## Instant Website Integration (No Manual Question-Time URL Setup)

Use this once per tenant to configure website/domain context automatically:

```bash
curl -X POST http://127.0.0.1:8000/v1/admin/website/integrate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-token>" \
  -d '{
    "tenant_id": "tnt_demo",
    "website_url": "https://your-website.com",
    "max_pages": 8,
    "max_depth": 1
  }'
```

What this does:

- Classifies the website into a primary/secondary domain
- Resolves a predefined preset (tenant map -> domain map -> default)
- Indexes website content for retrieval grounding
- Stores runtime website/domain settings for the tenant
- Enables V2 responses without passing URLs in each user query

For frontend integrations, this keeps setup minimal: integrate once per tenant and start sending user queries immediately.

## Configuration

`src/chatbot_api/config.py` is the source of truth for runtime configuration.

Important settings groups:

- Auth and JWT:
  - `CHATBOT_JWT_SECRET`, `CHATBOT_JWT_ALGORITHM`
  - `CHATBOT_JWT_CLAIM_TENANT_ID`, `CHATBOT_JWT_CLAIM_USER_ID`, `CHATBOT_JWT_CLAIM_ROLE`
  - `CHATBOT_ALLOW_DEV_TOKEN_AUTH`, `CHATBOT_LOCAL_LOGIN_ENABLED`
- Database:
  - `CHATBOT_SQLSERVER_HOST`, `CHATBOT_SQLSERVER_PORT`, `CHATBOT_SQLSERVER_USER`, `CHATBOT_SQLSERVER_PASSWORD`, `CHATBOT_SQLSERVER_DB`
  - `CHATBOT_DATABASE_URL`, `CHATBOT_DB_FALLBACK_TO_MOCK`
- V2 controls:
  - `CHATBOT_ENABLE_V2`
  - `CHATBOT_V2_RESEARCH_PROVIDER` (`skeleton` or `external`)
  - `CHATBOT_WEBSITE_PRESETS_JSON` (optional custom preset catalog)
  - `CHATBOT_WEBSITE_PRESET_MAP` (tenant->preset mapping, e.g. `tnt_demo:domain_fintech`)
- Security posture:
  - `CHATBOT_ENV`
  - `CHATBOT_STRICT_STARTUP_VALIDATION`
  - `CHATBOT_COOKIE_SECURE`, `CHATBOT_COOKIE_SAMESITE`
  - `CHATBOT_TRUSTED_HOSTS`, `CHATBOT_CORS_ALLOWED_ORIGINS`

Use `.env.example` as the baseline for local development.

## Built-in Domain Presets (Lean Production Set)

Default preset catalog includes open-domain references for:

1. `fintech`
2. `e_commerce`
3. `saas`
4. `education`
5. `healthcare`
6. `real_estate`
7. `travel_hospitality`
8. `food_restaurant`
9. `media_content`
10. `social_community`
11. `government_ngo`
12. `other`

The API uses these presets to deliver suggestion-style, website-grounded responses like improvement options, next steps, audits, and troubleshooting guidance.

## Production Baseline Checklist

At minimum, set the following before production deployment:

- `CHATBOT_ENV=production`
- `CHATBOT_JWT_SECRET=<strong secret from secret manager>`
- `CHATBOT_ALLOW_DEV_TOKEN_AUTH=false`
- `CHATBOT_LOCAL_LOGIN_ENABLED=false`
- `CHATBOT_COOKIE_SECURE=true`
- `CHATBOT_TRUSTED_HOSTS=<comma-separated allowed hosts>`
- `CHATBOT_CORS_ALLOWED_ORIGINS=<comma-separated explicit origins>`

With strict startup validation enabled, the app fails fast on unsafe production settings.

## Database Seeding

To load local SQL test data:

```bash
PYTHONPATH=src .venv/bin/python scripts/seed_test_db.py
```

Default test users include admin and standard users under `tnt_demo` with multi-month transactions and budget variance for precision testing.

If your SQL Server runs in Docker, verify the actual `sa` password from the container env (`MSSQL_SA_PASSWORD`) and use that value in `CHATBOT_SQLSERVER_PASSWORD`.

## Useful Scripts

- `scripts/seed_test_db.py` - seed SQL test data
- `scripts/generate_test_jwt.py` - generate HS256 JWTs for local testing
- `scripts/export_openapi.py` - export OpenAPI snapshot
- `scripts/check_openapi_contract.py` - validate OpenAPI snapshot drift
- `scripts/smoke_test_v2.sh` - smoke test V2 research endpoint
- `scripts/smoke_test_production_readiness.py` - production readiness smoke checks (indexing + V2 modes + out-of-scope handling)

## Testing

Run full suite:

```bash
PYTHONPATH=src .venv/bin/pytest -q
```

Run critical API/contract checks:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_api.py tests/test_regression_suite.py tests/test_v2_research_providers.py tests/test_openapi_contract.py
```

Run production smoke checks:

```bash
PYTHONPATH=src .venv/bin/python scripts/smoke_test_production_readiness.py
```

Run role-awareness regressions:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_regression_suite.py -k "website_improvement or spoof"
```

## Error Handling Contract

Error responses are normalized across endpoints as:

```json
{
  "error": {
    "code": "<MACHINE_CODE>",
    "message": "<human-readable message>",
    "request_id": "req_<id>",
    "retry_after_ms": 1234
  }
}
```

Notes:

- `retry_after_ms` is present for rate-limited responses (`429`) when applicable.
- Common mappings: `401 -> UNAUTHORIZED`, `403 -> FORBIDDEN`, `422 -> INVALID_REQUEST`, `429 -> RATE_LIMIT_EXCEEDED`, `500 -> INTERNAL_ERROR`.

## Role-Aware Behavior (User vs Admin)

- Role is enforced from validated JWT (`auth.role`), not from client payload fields.
- Non-admin users are blocked from website-improvement/audit guidance in both V1 and V2.
- Spoofed payload fields are ignored (for example `user_role: "admin"` in `/v2/research` or `metadata.auth_role: "admin"` in `/v1/chat`).
- Expected non-admin behavior for website-improvement prompts:
  - Status remains `200` with safe informational guidance.
  - Warning includes `admin_only_website_improvement`.

## Documentation

See `docs/README.md` for full documentation index, including:

- API reference and architecture
- Operations and release runbooks
- Client service model and internal operations SOP
