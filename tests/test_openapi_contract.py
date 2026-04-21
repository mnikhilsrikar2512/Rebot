import json
from pathlib import Path

from chatbot_api.main import app


def test_openapi_contract_snapshot_matches() -> None:
    snapshot = Path("openapi/openapi.v1.0.0-rc1.json")
    assert snapshot.exists(), "OpenAPI snapshot missing: openapi/openapi.v1.0.0-rc1.json"

    expected = json.loads(snapshot.read_text(encoding="utf-8"))
    actual = app.openapi()
    assert actual == expected


def test_openapi_v2_preview_snapshot_matches() -> None:
    snapshot = Path("openapi/openapi.v2.preview1.json")
    assert snapshot.exists(), "OpenAPI snapshot missing: openapi/openapi.v2.preview1.json"

    expected = json.loads(snapshot.read_text(encoding="utf-8"))
    actual = app.openapi()
    assert actual == expected
