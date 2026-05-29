-- Per-app role split for honeywatch.
-- Sourced from /docker-entrypoint-initdb.d/init.sh which supplies
-- INGESTOR_PW and API_PW via psql -v variable substitution.
-- Runs only on initial postgres data dir creation.

CREATE ROLE honeywatch_ingestor WITH LOGIN PASSWORD :'INGESTOR_PW';
CREATE ROLE honeywatch_api      WITH LOGIN PASSWORD :'API_PW';

GRANT USAGE ON SCHEMA public TO honeywatch_ingestor, honeywatch_api;

-- ingestor writes events and maintains geo cache.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT INSERT, SELECT, UPDATE, DELETE ON TABLES TO honeywatch_ingestor;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO honeywatch_ingestor;

-- api is read-only.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO honeywatch_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO honeywatch_api;

-- stream consumer for LISTEN/NOTIFY over the tailnet. It only runs LISTEN,
-- which is not governed by any privilege, and CONNECT is granted to PUBLIC by
-- default, so this role needs no grants at all - just LOGIN + password.
CREATE ROLE honeywatch_stream WITH LOGIN PASSWORD :'STREAM_PW';
