default:
    @just --list

# Bring up the dev stack (cowrie, postgres, ingestor, api, dashboard, grafana).
# Dashboard on http://localhost:8080, API on :5000, Grafana on :3000.
dev:
    docker compose up -d --build

# Tail logs. `just logs` follows everything; `just logs api ingestor` filters.
logs *services:
    docker compose logs -f {{services}}

# Stop and remove the dev stack.
down:
    docker compose down

# Run alembic migrations against the dev postgres. Idempotent; safe to re-run.
# The api entrypoint also runs this on boot -- use this recipe to apply a new
# migration without restarting the API container.
db-upgrade:
    docker compose exec api alembic upgrade head

# SSH into the local cowrie to generate real events. Type any password when
# prompted; cowrie logs both successful and failed attempts. Default user is
# root; override with `just attack admin`.
attack user="root":
    ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {{user}}@localhost || true

# Stream the raw cowrie JSON events -- the exact input the ingestor parses.
# Useful for eyeballing the wire format or capturing samples for tests.
cowrie-log:
    docker compose exec ingestor tail -f /logs/cowrie.json
