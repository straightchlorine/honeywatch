#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting gunicorn..."
exec gunicorn -b 0.0.0.0:5000 "src.app:create_app()"
