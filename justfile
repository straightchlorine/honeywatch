set dotenv-load := true

mod db

default:
    @just --list

# Bring up the dev stack.
dev:
    docker compose up -d --build

# Tail logs; `just logs api ingestor` filters.
logs *services:
    docker compose logs -f {{services}}

down:
    docker compose down

# SSH into the local cowrie to generate events; any password works.
attack user="root":
    ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {{user}}@localhost || true

# Stream the raw cowrie JSON the ingestor parses.
cowrie-log:
    docker compose exec ingestor tail -f /logs/cowrie.json

# Fetch GeoLite2 mmdb files into ingestor/data/; needs MAXMIND_* in .env.
fetch-mmdb:
    ./scripts/fetch-mmdb.sh ingestor/data

# Seed the dev DB with synthetic data for UI testing (WIPES all tables).
seed *args:
    cd api && POSTGRES_HOST=localhost POSTGRES_PORT="${POSTGRES_HOST_PORT:-5433}" ENVIRONMENT=development uv run python scripts/seed_dev.py {{args}}

# Any dashboard pnpm script: `just pnpm dev`, `just pnpm lint`, `just pnpm e2e`.
pnpm *args:
    cd dashboard && pnpm {{args}}

# Fast pytest against the dev postgres' test DB (`just dev` first).
test-api:
    cd api && POSTGRES_HOST=localhost POSTGRES_PORT="${POSTGRES_HOST_PORT:-5433}" POSTGRES_TEST_DB=honeywatch_test uv run --extra dev pytest -q

test-ingestor:
    cd ingestor && POSTGRES_HOST=localhost POSTGRES_PORT="${POSTGRES_HOST_PORT:-5433}" POSTGRES_TEST_DB=honeywatch_test uv run pytest -q

# Full CI mirror (minus the Playwright e2e; `just pnpm e2e` for that).
test:
    just db test-init
    for d in api ingestor; do (cd $d && uv run ruff check . && uv run ruff format --check . && uv run pyright) || exit 1; done
    just test-api
    just test-ingestor
    just pnpm install --frozen-lockfile
    just pnpm lint
    just pnpm build
    just pnpm test --coverage

# Full local gate: test suite plus OpenAPI drift check.
check: test openapi-check

# Dump the OpenAPI spec to api/openapi.json.
api-openapi:
    cd api && FLASK_APP=src.app:create_app FLASK_SECRET_KEY=openapi-dump ENVIRONMENT=development uv run flask openapi-dump --output openapi.json

# Regen backend spec + frontend TS SDK.
openapi-regen: api-openapi
    just pnpm openapi:gen

# CI drift gate: regen, then fail if committed spec or client drifted.
openapi-check: openapi-regen
    git add -A -- api/openapi.json dashboard/src/api/generated
    git diff --cached --exit-code -- api/openapi.json dashboard/src/api/generated

# Bump version everywhere and commit.
bump-version version:
    sed -i 's/^version = ".*"/version = "{{version}}"/' api/pyproject.toml ingestor/pyproject.toml
    sed -i 's/"version": ".*"/"version": "{{version}}"/' dashboard/package.json
    cd api && uv lock
    cd ingestor && uv lock
    git add api/pyproject.toml api/uv.lock ingestor/pyproject.toml ingestor/uv.lock dashboard/package.json
    git commit
