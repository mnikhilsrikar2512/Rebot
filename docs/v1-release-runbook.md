# V1 Release Runbook

Run these commands in order to finalize and ship V1.

## 1) Prepare Environment

```bash
cd /Users/bhargavnikhil/Desktop/chatbot
source .venv/bin/activate
cp .env.example .env
```

Set production-safe auth posture in `.env`:

- `CHATBOT_ALLOW_DEV_TOKEN_AUTH=false`
- `CHATBOT_JWT_SECRET=<strong-32-byte-plus-secret>`

## 2) Start Staging Stack

```bash
docker compose up -d --build
docker compose exec chatbot-api python scripts/seed_test_db.py
```

## 3) Run Automated Validation

```bash
PYTHONPATH=src pytest
PYTHONPATH=src python scripts/export_openapi.py --output openapi/openapi.v1.0.0-rc1.json
PYTHONPATH=src python scripts/check_openapi_contract.py --snapshot openapi/openapi.v1.0.0-rc1.json
```

## 4) Smoke Test Endpoints

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/metrics
curl http://127.0.0.1:8000/docs
```

## 5) Security and Policy Spot Checks

- Verify non-admin platform query returns `403`.
- Verify cross-tenant access returns `403`.
- Verify `/v1/alerts` returns threshold payload.

## 6) Contract Freeze

- Confirm `openapi/openapi.v1.0.0-rc1.json` is attached to release PR.
- Complete `docs/v1-contract-freeze-checklist.md`.
- Fill `docs/release-notes-template.md`.

## 7) Tag and Release

```bash
git add .
git commit -m "release: finalize v1.0.0-rc1"
git tag v1.0.0-rc1
```

## 8) Promote to V1

After pilot sign-off:

```bash
git tag v1.0.0
```
