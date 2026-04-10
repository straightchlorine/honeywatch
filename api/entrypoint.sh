#!/bin/sh
set -e

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting gunicorn..."
exec uv run gunicorn -b 0.0.0.0:5000 "src.app:create_app()"
