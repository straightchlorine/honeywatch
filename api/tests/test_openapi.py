"""Privacy + completeness gates on the generated OpenAPI spec.

The spec drives codegen for ``dashboard/src/api/schema.d.ts``. Two
guarantees enforced here:

1. **Privacy gate**: the string ``src_ip`` MUST NOT appear anywhere in the
   spec - not in a schema field name, not in an example, not in a path
   parameter. The frontend literally cannot ask for it.
2. **Coverage gate**: every ``/api/v1/...`` route declared by the blueprints
   must be documented under ``paths``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OPENAPI_URL = "/api/v1/openapi.json"


def test_openapi_endpoint_returns_200(client: Any) -> None:
    response = client.get(OPENAPI_URL)
    assert response.status_code == 200
    spec = response.get_json()
    assert isinstance(spec, dict)
    assert "paths" in spec
    assert "components" in spec


def test_openapi_no_ip_addresses_anywhere(client: Any) -> None:
    """Privacy contract: no IP address field crosses the API.

    Neither the attacker source (``src_ip``) nor the honeypot destination
    (``dst_ip``) may leak into the OpenAPI spec. Substring check on the
    serialized spec covers schema field names, example values, descriptions,
    and path parameter names in one pass.
    """
    response = client.get(OPENAPI_URL)
    assert response.status_code == 200
    serialized = json.dumps(response.get_json())
    assert "src_ip" not in serialized
    assert "dst_ip" not in serialized


def test_openapi_documents_core_paths(client: Any) -> None:
    """Every blueprint-declared route should be documented."""
    response = client.get(OPENAPI_URL)
    assert response.status_code == 200
    paths = response.get_json()["paths"]

    expected = {
        "/api/v1/sessions/",
        "/api/v1/sessions/{session_id}",
        "/api/v1/stats/totals",
        "/api/v1/stats/top-passwords",
        "/api/v1/stats/top-countries",
        "/api/v1/stats/top-credentials",
        "/api/v1/stats/auth-outcomes",
        "/api/v1/stats/password-composition",
        "/api/v1/stats/passwords-by-length",
        "/api/v1/stats/activity",
        "/api/v1/stats/trend",
        "/api/v1/stats/heatmap",
        "/health",
        "/health/ready",
    }
    missing = expected - paths.keys()
    assert not missing, f"undocumented paths: {sorted(missing)}"


def test_openapi_sessions_schema_has_no_ip_field(client: Any) -> None:
    """Explicit schema-level assertion (defense in depth vs substring check)."""
    response = client.get(OPENAPI_URL)
    spec = response.get_json()
    schemas = spec.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        assert "src_ip" not in props, f"schema {name!r} declares src_ip"
        assert "dst_ip" not in props, f"schema {name!r} declares dst_ip"


def test_openapi_every_operation_has_operationId(client: Any) -> None:
    """Every documented operation must declare an operationId.

    operationIds drive method names in the generated TypeScript client; a
    missing one yields an opaque ``pathSomethingGet`` function instead of a
    semantic name.
    """
    response = client.get(OPENAPI_URL)
    spec = response.get_json()
    methods = {"get", "post", "put", "delete", "patch"}
    missing: list[str] = []
    for path, path_item in spec["paths"].items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method not in methods or not isinstance(op, dict):
                continue
            if "operationId" not in op:
                missing.append(f"{method.upper()} {path}")
    assert not missing, f"operations missing operationId: {missing}"


def test_openapi_session_detail_declares_404(client: Any) -> None:
    """The session detail endpoint must document a 404 response."""
    response = client.get(OPENAPI_URL)
    spec = response.get_json()
    responses = spec["paths"]["/api/v1/sessions/{session_id}"]["get"]["responses"]
    assert "404" in responses, f"expected 404 documented, got {sorted(responses)}"


def test_openapi_snapshot_matches_committed(client: Any) -> None:
    """The committed ``api/openapi.json`` must match a fresh dump from the app.

    Drift here means codegen consumers see a different spec than CI.
    Regenerate via the spec-dump justfile recipe to refresh the snapshot.
    """
    snapshot_path = Path(__file__).resolve().parents[1] / "openapi.json"
    assert snapshot_path.exists(), (
        f"committed openapi.json missing at {snapshot_path}; "
        "regenerate via `just api-openapi`"
    )
    with snapshot_path.open() as fh:
        committed = json.load(fh)

    response = client.get(OPENAPI_URL)
    assert response.status_code == 200
    fresh = response.get_json()
    # Mirror `flask openapi-dump`: committed snapshot has `servers` stripped so
    # the host the spec was dumped against doesn't leak into the artifact.
    fresh.pop("servers", None)

    if committed != fresh:
        committed_keys = set(committed.get("paths", {}).keys())
        fresh_keys = set(fresh.get("paths", {}).keys())
        only_committed = sorted(committed_keys - fresh_keys)
        only_fresh = sorted(fresh_keys - committed_keys)
        committed_schemas = set(
            committed.get("components", {}).get("schemas", {}).keys()
        )
        fresh_schemas = set(fresh.get("components", {}).get("schemas", {}).keys())
        only_committed_schemas = sorted(committed_schemas - fresh_schemas)
        only_fresh_schemas = sorted(fresh_schemas - committed_schemas)
        diff_summary = {
            "paths_only_in_committed": only_committed,
            "paths_only_in_fresh": only_fresh,
            "schemas_only_in_committed": only_committed_schemas,
            "schemas_only_in_fresh": only_fresh_schemas,
        }
        raise AssertionError(
            "committed api/openapi.json is out of date - regenerate via "
            "`just api-openapi`. drift summary:\n" + json.dumps(diff_summary, indent=2)
        )
