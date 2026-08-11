-- Per-app role split; only runs on initial PG init.

CREATE ROLE honeywatch_ingestor WITH LOGIN PASSWORD :'INGESTOR_PW';
CREATE ROLE honeywatch_api      WITH LOGIN PASSWORD :'API_PW';

GRANT USAGE ON SCHEMA public TO honeywatch_ingestor, honeywatch_api;

-- Ingestor maintains geo cache.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT INSERT, SELECT, UPDATE, DELETE ON TABLES TO honeywatch_ingestor;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO honeywatch_ingestor;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO honeywatch_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO honeywatch_api;
