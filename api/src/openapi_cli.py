"""Helpers behind the `flask openapi-dump` command.

Kept out of app.py so the dump contract (sorted keys, trailing newline, no
`servers` block) can be tested without booting Flask.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, cast

import click
from flask import Flask
from flask_smorest import Api


def build_spec_dict(smorest_api: Api) -> dict[str, Any]:
    """Materialize the flask-smorest spec to a plain dict.

    Shared by the runtime cache and dump CLI to keep served and committed specs
    in sync.

    Arguments:
      smorest_api: Api — the flask-smorest instance

    Returns:
      dict[str, Any] — the OpenAPI spec as a dictionary

    Raises:
      RuntimeError: if flask-smorest spec is not initialized
    """
    spec_obj = smorest_api.spec
    if spec_obj is None:
        raise RuntimeError("flask-smorest spec not initialised")
    return cast(dict[str, Any], spec_obj.to_dict())


def dump_spec(spec: dict[str, Any], output: pathlib.Path) -> int:
    """Write OpenAPI spec to output with sorted keys and no `servers` block.

    Arguments:
      spec: dict[str, Any] — OpenAPI spec to write
      output: pathlib.Path — file path to write to

    Returns:
      int — bytes written

    How it works:
      `servers` is stripped to keep the committed snapshot environment-independent.
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
        try:
            spec = build_spec_dict(smorest_api)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(f"failed to build OpenAPI spec: {exc}") from exc
        path = pathlib.Path(output)
        try:
            written = dump_spec(spec, path)
        except OSError as exc:
            raise click.ClickException(f"failed to write {path}: {exc}") from exc
        click.echo(f"wrote {path} ({written} bytes)")
