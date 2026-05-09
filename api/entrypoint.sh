#!/bin/sh
set -e

# Migrations run in a separate one-shot api-migrate service (see
# docker-compose.prod.yml) using bootstrap Postgres credentials. The
# api service connects as honeywatch_api (read-only) and must not
# attempt schema changes.

exec gunicorn \
  -b 0.0.0.0:5000 \
  -w 2 --threads 4 \
  --timeout 30 \
  --max-requests 1000 --max-requests-jitter 50 \
  --access-logfile - --error-logfile - \
  "src.app:create_app()"
