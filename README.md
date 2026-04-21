# Universal Chatbot API

FastAPI service for a tenant-aware chatbot with JWT auth, SQL Server-backed data access, tool/webhook runtime support, metrics, and a small browser frontend.

## Highlights

- `POST /v1/chat`, `POST /v1/sessions`, and auth endpoints for local development
- SQL Server or mock adapter mode
- Tenant and user scope enforcement
- External research and v2 research endpoints
- Prometheus-style metrics at `/metrics`
- Browser frontend at `/`

## Repository Layout

```text
src/chatbot_api/   API, auth, adapters, and services
frontend/          Small web UI for manual testing
scripts/           DB seeding, OpenAPI export, smoke checks
tests/             API and contract regression tests
docs/              Product, ops, and release runbooks
openapi/           Exported OpenAPI specifications
```

## Quick Start

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Create a local env file from the example.

```bash
cp .env.example .env
```

4. Start the API.

```bash
PYTHONPATH=src uvicorn chatbot_api.main:app --reload
```

5. Open the app.

- API docs: `http://127.0.0.1:8000/docs`
- Frontend: `http://127.0.0.1:8000/`

## Environment Variables

`src/chatbot_api/config.py` is the source of truth for configuration. The most important settings are:

- `CHATBOT_JWT_SECRET`
- `CHATBOT_SQLSERVER_HOST`, `CHATBOT_SQLSERVER_PORT`, `CHATBOT_SQLSERVER_USER`, `CHATBOT_SQLSERVER_PASSWORD`, `CHATBOT_SQLSERVER_DB`
- `CHATBOT_ALLOW_DEV_TOKEN_AUTH`
- `CHATBOT_LOCAL_LOGIN_ENABLED`
- `CHATBOT_EXTERNAL_RESEARCH_ENABLED`
- `CHATBOT_TENANT_DOMAIN_MAP`
- `CHATBOT_DB_FALLBACK_TO_MOCK`

Use `.env.example` as the starting point for local development.

## Database Seeding

If you want the SQL Server test data used by the repo, run:

```bash
PYTHONPATH=src python scripts/seed_test_db.py
```

## Useful Scripts

- `scripts/seed_test_db.py` seeds the local SQL Server test database
- `scripts/generate_test_jwt.py` creates a signed test token
- `scripts/export_openapi.py` exports the API schema
- `scripts/check_openapi_contract.py` validates the OpenAPI contract
- `scripts/smoke_test_v2.sh` exercises the v2 research flow

## Testing

```bash
pytest
```

The suite covers auth, chat flows, v2 research providers, and the OpenAPI contract.

## Notes

- Local login is enabled by default for developer workflows.
- If SQL Server is configured, the adapter switches away from mock mode automatically.
- The app returns an `X-Request-Id` header on API responses for traceability.
