"""Top-level openapi-dump helpers.

Extracted from ``app.py`` so the dump contract (sort_keys=True, trailing
newline, ``servers`` stripped) is unit-testable without booting Flask.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, cast

import click
from flask import Flask
from flask_smorest import Api


def dump_spec(spec: dict[str, Any], output: pathlib.Path) -> int:
    """Write ``spec`` to ``output`` with the deterministic dump contract.

    Returns the number of bytes written. Raises ``OSError`` on disk errors
    (callers should map to ``click.ClickException`` for CI-friendly errors).
    """
    body = json.dumps(_strip_servers(spec), indent=2, sort_keys=True) + "\n"
    output.write_text(body, encoding="utf-8")
    return len(body)


def _strip_servers(spec: dict[str, Any]) -> dict[str, Any]:
    out = dict(spec)
    out.pop("servers", None)
    return out


def register_openapi_cli(app: Flask, smorest_api: Api) -> None:
    @app.cli.command("openapi-dump")
    @click.option(
        "--output",
        "-o",
        default="openapi.json",
        type=click.Path(dir_okay=False, writable=True),
        show_default=True,
        help="Path to write the spec to (relative to CWD).",
    )
    def openapi_dump(output: str) -> None:  # pyright: ignore[reportUnusedFunction]
        spec_obj = smorest_api.spec
        if spec_obj is None:
            raise click.ClickException("flask-smorest spec not initialised")
        try:
            spec = cast(dict[str, Any], spec_obj.to_dict())
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(f"failed to build OpenAPI spec: {exc}") from exc
        path = pathlib.Path(output)
        try:
            written = dump_spec(spec, path)
        except OSError as exc:
            raise click.ClickException(f"failed to write {path}: {exc}") from exc
        click.echo(f"wrote {path} ({written} bytes)")
