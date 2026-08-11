#!/bin/sh
# Wrapper to pass per-role passwords to init.sql via psql -v.
set -eu

: "${POSTGRES_INGESTOR_PASSWORD:?POSTGRES_INGESTOR_PASSWORD must be set}"
: "${POSTGRES_API_PASSWORD:?POSTGRES_API_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 \
    -v INGESTOR_PW="$POSTGRES_INGESTOR_PASSWORD" \
    -v API_PW="$POSTGRES_API_PASSWORD" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -f /etc/honeywatch/init.sql
