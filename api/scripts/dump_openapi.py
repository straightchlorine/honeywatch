"""Emit /api/openapi.json to disk for offline codegen + CI drift check.

Run from the api/ directory:

    cd api && uv run python scripts/dump_openapi.py

Writes the spec to api/openapi.json (relative to the repository root).
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "api"
OUTPUT_PATH = API_DIR / "openapi.json"

# Allow `from src.app import create_app` when invoked from any cwd.
sys.path.insert(0, str(API_DIR))

# Pure-spec dump must not require a live database.
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("FLASK_SECRET_KEY", "openapi-dump")

from src.app import create_app  # noqa: E402
from src.config import TestingConfig  # noqa: E402


def main() -> int:
    app = create_app(TestingConfig)
    with app.test_client() as client:
        response = client.get("/api/openapi.json")
        if response.status_code != 200:
            print(
                f"GET /api/openapi.json returned {response.status_code}",
                file=sys.stderr,
            )
            return 1
        spec = response.get_json()
    OUTPUT_PATH.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
