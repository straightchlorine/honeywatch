# Dev database. One postgres container hosts `${POSTGRES_DB}` and
# `honeywatch_test` (test suite; transactions roll back per-test).

upgrade:
    docker compose exec api alembic upgrade head

downgrade:
    docker compose exec api alembic downgrade -1

heads:
    docker compose exec api alembic heads

# Autogenerate a revision from the model diff; review it before `just db upgrade`.
revision message:
    docker compose exec api alembic revision --autogenerate -m "{{message}}"

# Empty revision for data migrations, CONCURRENTLY, etc.
revision-empty message:
    docker compose exec api alembic revision -m "{{message}}"

shell:
    docker compose exec postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"

# Restore a gzipped pg_dumpall dump. WIPES data. Only the `${POSTGRES_DB}` section replays; DROP ROLE/GRANTs are skipped (they'd lock services out).
restore file:
    docker compose stop api ingestor
    docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
      -c "DROP SCHEMA IF EXISTS public CASCADE" -c "CREATE SCHEMA public"
    gzip -dc {{file}} \
      | awk -v db="$POSTGRES_DB" \
          '$0 == "\\connect " db {f=1; seen=1; next} \
           f && /^-- Database "/ {f=0} \
           f && /^(GRANT |REVOKE |ALTER DEFAULT PRIVILEGES )/ {next} \
           f {print} \
           END {if (!seen) {print "no \\connect " db " section in dump" > "/dev/stderr"; exit 1}}' \
      | docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
    docker compose start api ingestor

test-init:
    docker compose up -d --wait postgres
    -docker compose exec -T postgres createdb -U "$POSTGRES_USER" honeywatch_test 2>/dev/null
    @echo "honeywatch_test ready"

test-shell:
    docker compose exec postgres psql -U "$POSTGRES_USER" honeywatch_test

test-reset:
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS honeywatch_test;"
    @just db test-init
