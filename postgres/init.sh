#!/bin/sh
# Wrapper for init.sql so we can pass per-role passwords via psql -v.
# postgres entrypoint runs *.sh files with the postgres superuser env set.
set -eu

: "${POSTGRES_INGESTOR_PASSWORD:?POSTGRES_INGESTOR_PASSWORD must be set}"
: "${POSTGRES_API_PASSWORD:?POSTGRES_API_PASSWORD must be set}"
: "${POSTGRES_STREAM_PASSWORD:?POSTGRES_STREAM_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 \
    -v INGESTOR_PW="$POSTGRES_INGESTOR_PASSWORD" \
    -v API_PW="$POSTGRES_API_PASSWORD" \
    -v STREAM_PW="$POSTGRES_STREAM_PASSWORD" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -f /etc/honeywatch/init.sql
