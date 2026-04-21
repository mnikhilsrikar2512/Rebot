# V1 Contract Freeze Checklist

Use this checklist before tagging `v1.0.0-rc1` / `v1.0.0`.

- [ ] Export OpenAPI snapshot:
  - `PYTHONPATH=src python scripts/export_openapi.py --output openapi/openapi.v1.0.0-rc1.json`
- [ ] Verify all production endpoints are present in snapshot:
  - auth-protected endpoints
  - streaming behavior for `/v1/chat`
  - tools/webhooks/metrics endpoints
- [ ] Confirm no breaking response shape changes since previous snapshot.
- [ ] Validate error envelope consistency (`error.code`, `error.message`, `error.request_id`).
- [ ] Run tests and save run artifact:
  - `PYTHONPATH=src pytest`
- [ ] Review rate-limit settings and documented defaults.
- [ ] Review tenant isolation behavior and cross-tenant denial checks.
- [ ] Confirm JWT-only mode in staging/prod (`CHATBOT_ALLOW_DEV_TOKEN_AUTH=false`).
- [ ] Attach OpenAPI snapshot and release notes to release PR.
