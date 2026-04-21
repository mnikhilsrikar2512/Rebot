from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatbot_api.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OpenAPI snapshot contract")
    parser.add_argument(
        "--snapshot",
        default="openapi/openapi.v1.0.0-rc1.json",
        help="Path to expected OpenAPI snapshot",
    )
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        raise SystemExit(f"Snapshot file not found: {snapshot_path}")

    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    actual = app.openapi()

    if actual != expected:
        raise SystemExit(
            "OpenAPI contract drift detected. "
            "Re-export intentionally via scripts/export_openapi.py and review changes."
        )

    print("OpenAPI contract check passed")


if __name__ == "__main__":
    main()
