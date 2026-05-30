#!/usr/bin/env bash
# Local smoke test: brings up prod postgres with TLS in an isolated compose
# project and asserts the tailnet honeywatch_stream role works over SSL only
# (non-ssl rejected, writes denied, LISTEN allowed). Run ./gen.sh first.
# Needs POSTGRES_USER/POSTGRES_DB - loaded from .env when run outside `just`.
set -euo pipefail

dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$dir/../.." && pwd)

# `just` exports .env already (set dotenv-load); load it for direct runs too.
[ -f "$repo/.env" ] && { set -a; . "$repo/.env"; set +a; }

# Test-only values; the host port binds are reset below so this is safe even
# if the host already runs postgres on 5432.
export TS_IP=127.0.0.1 POSTGRES_STREAM_PASSWORD=streampw
export POSTGRES_API_PASSWORD=x POSTGRES_INGESTOR_PASSWORD=x
export API_VERSION=unused INGESTOR_VERSION=unused

ovr=$(mktemp --suffix=.yml)
printf 'services:\n  postgres:\n    ports: !reset []\n' >"$ovr"
dc() { docker compose -p hw-tlstest -f "$repo/docker-compose.prod.yml" -f "$ovr" "$@"; }
cleanup() {
  docker network disconnect hw-tnet honeywatch-db 2>/dev/null || true
  docker network rm hw-tnet 2>/dev/null || true
  dc down -v 2>/dev/null || true
  rm -f "$ovr"
}
trap cleanup EXIT

dc up -d postgres
for _ in $(seq 1 30); do
  docker exec honeywatch-db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1 && break || sleep 1
done

echo "== ssl status (expect on) =="
docker exec honeywatch-db psql -U "$POSTGRES_USER" -c "show ssl"
echo "== honeywatch_stream role (expect exists, no grants) =="
docker exec honeywatch-db psql -U "$POSTGRES_USER" -c "\du honeywatch_stream"

docker network create --subnet 100.64.0.0/24 hw-tnet
docker network connect hw-tnet honeywatch-db
DBIP=$(docker inspect -f '{{(index .NetworkSettings.Networks "hw-tnet").IPAddress}}' honeywatch-db)
run() { docker run --rm --network hw-tnet -e PGPASSWORD="$POSTGRES_STREAM_PASSWORD" postgres:16-alpine \
          psql "host=$DBIP user=honeywatch_stream dbname=$POSTGRES_DB $1" -c "$2"; }

echo "== non-ssl tailnet must be REJECTED =="
if run "sslmode=disable" "SELECT 1"; then echo "FAIL: non-ssl accepted"; exit 1; else echo "OK rejected"; fi
echo "== ssl tailnet must SUCCEED =="
run "sslmode=require" "SELECT 1"
echo "== write/DDL must be DENIED (no grants) =="
if run "sslmode=require" "CREATE TABLE hw_probe(i int)"; then echo "FAIL: stream created a table"; exit 1; else echo "OK denied"; fi
echo "== LISTEN must be allowed =="
run "sslmode=require" "LISTEN new_session"
echo "ALL TLS CHECKS PASSED"
