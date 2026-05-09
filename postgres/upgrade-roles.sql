-- One-off upgrade script for existing deployments where postgres-data
-- already has data and init.sh did NOT run on fresh init.
--
-- Apply against the running container as the bootstrap superuser:
--
--   docker compose -f docker-compose.prod.yml exec -e PGPASSWORD="$POSTGRES_PASSWORD" \
--     postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--     -v INGESTOR_PW="$POSTGRES_INGESTOR_PASSWORD" \
--     -v API_PW="$POSTGRES_API_PASSWORD" \
--     -f /etc/honeywatch/upgrade-roles.sql
--
-- (Mount this file into the container first, e.g. via a temporary
-- compose override, or copy with `docker cp postgres/upgrade-roles.sql
-- honeywatch-db:/tmp/`.)
--
-- Idempotent: re-running is safe.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'honeywatch_ingestor') THEN
        EXECUTE format('CREATE ROLE honeywatch_ingestor WITH LOGIN PASSWORD %L', :'INGESTOR_PW');
    ELSE
        EXECUTE format('ALTER ROLE honeywatch_ingestor WITH LOGIN PASSWORD %L', :'INGESTOR_PW');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'honeywatch_api') THEN
        EXECUTE format('CREATE ROLE honeywatch_api WITH LOGIN PASSWORD %L', :'API_PW');
    ELSE
        EXECUTE format('ALTER ROLE honeywatch_api WITH LOGIN PASSWORD %L', :'API_PW');
    END IF;
END$$;

GRANT USAGE ON SCHEMA public TO honeywatch_ingestor, honeywatch_api;

-- Default privileges for FUTURE tables (matches postgres/init.sql).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT INSERT, SELECT, UPDATE, DELETE ON TABLES TO honeywatch_ingestor;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO honeywatch_ingestor;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO honeywatch_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO honeywatch_api;

-- Backfill privileges on EXISTING tables/sequences.
GRANT INSERT, SELECT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO honeywatch_ingestor;
GRANT USAGE,  SELECT                ON ALL SEQUENCES IN SCHEMA public TO honeywatch_ingestor;
GRANT SELECT                        ON ALL TABLES    IN SCHEMA public TO honeywatch_api;
GRANT SELECT                        ON ALL SEQUENCES IN SCHEMA public TO honeywatch_api;
