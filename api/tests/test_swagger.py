"""Swagger UI and ReDoc routes must render after the static asset move."""

from __future__ import annotations

from typing import Any


def test_swagger_route_200(client: Any) -> None:
    response = client.get("/api/v1/swagger")
    assert response.status_code == 200
    assert b"swagger" in response.data.lower()


def test_redoc_route_200(client: Any) -> None:
    response = client.get("/api/v1/redoc")
    assert response.status_code == 200
    assert b"redoc" in response.data.lower()


def test_static_swagger_index_served(client: Any) -> None:
    response = client.get("/static/swagger-ui/index.html")
    assert response.status_code == 200
    assert b"<html" in response.data.lower()
