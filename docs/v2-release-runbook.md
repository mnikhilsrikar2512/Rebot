# V2 Release Runbook

Run these commands in order to roll out V2 safely.

## 1) Prepare Environment

```bash
cd /Users/bhargavnikhil/Desktop/chatbot
source .venv/bin/activate
cp .env.example .env
```

Set V2 rollout flags in `.env`:

- `CHATBOT_ENABLE_V2=true`
- `CHATBOT_V2_RESEARCH_PROVIDER=skeleton`

## 2) Start Staging Stack

```bash
docker compose up -d --build
docker compose exec chatbot-api python scripts/seed_test_db.py
```

## 3) Run Validation and Contract Checks

```bash
.venv/bin/pytest -q tests/test_v2_research_providers.py tests/test_api.py tests/test_regression_suite.py tests/test_openapi_contract.py
PYTHONPATH=src python scripts/export_openapi.py --output openapi/openapi.v2.preview1.json
PYTHONPATH=src python scripts/check_openapi_contract.py --snapshot openapi/openapi.v2.preview1.json
```

## 4) Smoke Test V2 Endpoint

```bash
./scripts/smoke_test_v2.sh
```

Expected result:

- V2 with `skeleton` provider returns concise summary + recommendations.
- No auth errors, tenant-scope violations, or request-shape failures.

## 5) Switch Provider to External (Same Endpoint)

Update staging env:

- `CHATBOT_V2_RESEARCH_PROVIDER=external`

Restart deployment and rerun smoke test:

```bash
./scripts/smoke_test_v2.sh
```

Expected result:

- `/v2/research` returns external-backed recommendations.
- Domain policy and allowlist enforcement remain active.

## 6) Rollback Plan

- Fast rollback: set `CHATBOT_V2_RESEARCH_PROVIDER=skeleton`.
- Full rollback: set `CHATBOT_ENABLE_V2=false`.

## 7) Promote to Production

- Start with `skeleton` provider and monitor.
- Switch to `external` only after stable metrics/error rate.
