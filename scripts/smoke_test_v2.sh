#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
TENANT_ID="${TENANT_ID:-tnt_demo}"
USER_ID="${USER_ID:-usr_alex}"
QUERY="${QUERY:-give my overview}"

if [[ -z "${BEARER_TOKEN:-}" ]]; then
  echo "ERROR: BEARER_TOKEN is required"
  echo "Set BEARER_TOKEN to a valid JWT for tenant ${TENANT_ID}"
  exit 1
fi

body=$(python3 - <<PY
import json
print(json.dumps({
  "tenant_id": "${TENANT_ID}",
  "user_id": "${USER_ID}",
  "query": "${QUERY}",
  "sources": [{"url": "https://www.investopedia.com/terms/b/budget.asp"}],
  "max_sources": 2,
  "verbose": False,
}))
PY
)

echo "Calling ${API_BASE_URL}/v2/research ..."
status=$(curl -s -o /tmp/v2_smoke_response.json -w "%{http_code}" \
  -X POST "${API_BASE_URL}/v2/research" \
  -H "Authorization: Bearer ${BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${body}")

echo "HTTP ${status}"
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('/tmp/v2_smoke_response.json').read_text())
print(json.dumps(payload, indent=2)[:2000])
PY

if [[ "${status}" != "200" ]]; then
  echo "V2 smoke test failed"
  exit 2
fi

echo "V2 smoke test passed"
