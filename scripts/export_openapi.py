from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatbot_api.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema snapshot")
    parser.add_argument(
        "--output",
        default="openapi/openapi.snapshot.json",
        help="Output file path for OpenAPI JSON",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"OpenAPI exported to {output_path}")


if __name__ == "__main__":
    main()
