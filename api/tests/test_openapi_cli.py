"""`flask openapi-dump` CLI: deterministic, server-stripped, trailing newline.

This is the contract the committed snapshot is regenerated against; a drift
here silently breaks dashboard codegen reproducibility.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from src.openapi_cli import dump_spec


def test_dump_spec_strips_servers_and_sorts_keys(tmp_path: pathlib.Path) -> None:
    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "servers": [{"url": "https://evil.example/"}],
        "paths": {"/b": {}, "/a": {}},
        "info": {"title": "test"},
    }
    out = tmp_path / "openapi.json"
    n = dump_spec(spec, out)

    text = out.read_text()
    assert text.endswith("\n")
    assert n == len(text)

    loaded = json.loads(text)
    assert "servers" not in loaded
    assert loaded["paths"] == {"/a": {}, "/b": {}}
    assert list(loaded.keys()) == sorted(loaded.keys())


def test_openapi_dump_cli_writes_file(app: Any, tmp_path: pathlib.Path) -> None:
    output = tmp_path / "out.json"
    runner = app.test_cli_runner()
    result = runner.invoke(args=["openapi-dump", "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert "wrote" in result.output
    assert output.exists()
    text = output.read_text()
    assert text.endswith("\n")
    spec = json.loads(text)
    assert "servers" not in spec
    assert "paths" in spec
