#!/usr/bin/env python3
"""Generate OpenAPI JSON specification from the FastAPI application.

Writes docs/openapi.json for frontend client generation.
"""

from __future__ import annotations

import json
from pathlib import Path

from flame.api.main import create_app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"


def generate_openapi() -> None:
    app = create_app()
    openapi_schema = app.openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"OpenAPI schema successfully written to {OUTPUT_PATH}")


if __name__ == "__main__":
    generate_openapi()
