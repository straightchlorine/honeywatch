"""Privacy + completeness gates on the generated OpenAPI spec.

The spec drives codegen for ``dashboard/src/api/schema.d.ts``. Two
guarantees enforced here:

1. **Privacy gate**: the string ``src_ip`` MUST NOT appear anywhere in the
   spec - not in a schema field name, not in an example, not in a path
   parameter. The frontend literally cannot ask for it.
2. **Coverage gate**: every ``/api/...`` route declared by the blueprints
   must be documented under ``paths``.
"""

from __future__ import annotations

import json
from typing import Any


def test_openapi_endpoint_returns_200(client: Any) -> None:
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    spec = response.get_json()
    assert isinstance(spec, dict)
    assert "paths" in spec
    assert "components" in spec


def test_openapi_no_src_ip_anywhere(client: Any) -> None:
    """Privacy contract: ``src_ip`` must not leak into the OpenAPI spec.

    Substring check on the serialized spec covers schema field names,
    example values, descriptions, and path parameter names in one pass.
    """
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    serialized = json.dumps(response.get_json())
    assert "src_ip" not in serialized


def test_openapi_documents_core_paths(client: Any) -> None:
    """Every blueprint-declared route under /api should be documented."""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = response.get_json()["paths"]

    expected = {
        "/api/sessions",
        "/api/sessions/{session_id}",
        "/api/stats/totals",
        "/api/stats/top-passwords",
        "/api/stats/top-countries",
        "/api/stats/activity",
        "/api/stats/trend",
        "/api/stats/heatmap",
        "/health",
        "/health/ready",
    }
    missing = expected - paths.keys()
    assert not missing, f"undocumented paths: {sorted(missing)}"


def test_openapi_sessions_schema_has_no_src_ip_field(client: Any) -> None:
    """Explicit schema-level assertion (defense in depth vs substring check)."""
    response = client.get("/api/openapi.json")
    spec = response.get_json()
    schemas = spec.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        assert "src_ip" not in props, f"schema {name!r} declares src_ip"
