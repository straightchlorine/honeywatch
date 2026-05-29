#!/bin/sh
set -e

# Migrations run in a separate one-shot api-migrate service (see
# docker-compose.prod.yml).

# See gunicorn.conf.py for config
exec gunicorn -c gunicorn.conf.py "src.app:create_app()"
