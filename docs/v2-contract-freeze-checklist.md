# V2 Contract Freeze Checklist

Use this checklist before promoting V2 in staging/production.

- [ ] Enable V2 in staging:
  - `CHATBOT_ENABLE_V2=true`
  - `CHATBOT_V2_RESEARCH_PROVIDER=skeleton`
- [ ] Export OpenAPI snapshot for V2 preview:
  - `PYTHONPATH=src python scripts/export_openapi.py --output openapi/openapi.v2.preview1.json`
- [ ] Validate contract against snapshot:
  - `PYTHONPATH=src python scripts/check_openapi_contract.py --snapshot openapi/openapi.v2.preview1.json`
- [ ] Verify `/v2/research` response shape is stable for both providers (`skeleton`, `external`).
- [ ] Verify feature-flag behavior:
  - V2 disabled => `403`
  - V2 enabled => `/v2/research` works
- [ ] Verify provider-switch behavior on same endpoint:
  - `CHATBOT_V2_RESEARCH_PROVIDER=skeleton`
  - `CHATBOT_V2_RESEARCH_PROVIDER=external`
- [ ] Run regression tests and save artifacts:
  - `.venv/bin/pytest -q tests/test_v2_research_providers.py tests/test_api.py tests/test_regression_suite.py tests/test_openapi_contract.py`
- [ ] Verify negative-path checks:
  - invalid provider => `500`
  - malformed source URL => `400`
  - source fetch failures => `503`
  - tenant mismatch => `403`
- [ ] Attach OpenAPI snapshot and V2 rollout notes to release PR.
