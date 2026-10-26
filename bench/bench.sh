#!/usr/bin/env bash
# Isolated Postgres for the sessions-list benchmarks: a prod dump, capped like prod.
# Never touches the dev stack (honeywatch-db on 5433) or production.
#
#   bench.sh up        create the container (prod-like caps, pg_stat_statements on)
#   bench.sh restore   load honeywatch-prod-data.gz (a pg_dumpall), about 5 min
#   bench.sh prepare   set role passwords, run alembic from BENCH_API_DIR, ANALYZE
#   bench.sh restart   restart Postgres (empties shared_buffers, not the host page cache)
#   bench.sh env       print the exports measure.py and alembic need: eval "$(bench.sh env)"
#   bench.sh psql ...  psql as the superuser in the bench database; args and stdin pass through
#   bench.sh status    caps, row counts, alembic version, pg_stat_statements
#   bench.sh down      remove the container and its data directory
#
# One container per release. For a second one, set another name, port and data directory:
#
#   BENCH_NAME=hw-bench-pg-0.8.2 BENCH_PORT=5498 \
#   BENCH_DATA=$HOME/.cache/hw-bench-pg-0.8.2 bench.sh up
#
# BENCH_API_DIR is the checkout whose api/ gets migrated. Point it at the release's
# worktree, or the schema will be the wrong one.
set -euo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
REPO="$(cd "$(dirname "$SELF")/.." && pwd)"
API_DIR="${BENCH_API_DIR:-$REPO}/api"
NAME="${BENCH_NAME:-hw-bench-pg}"
PORT="${BENCH_PORT:-5499}"
IMAGE="${BENCH_IMAGE:-postgres:16-alpine}"    # postgres:16 (Debian) enables JIT
DATA="${BENCH_DATA:-$HOME/.cache/hw-bench-pg}"
DUMP="${BENCH_DUMP:-$REPO/honeywatch-prod-data.gz}"
MEM="${BENCH_MEM:-1g}"                        # prod postgres limit
CPUS="${BENCH_CPUS:-1.5}"                     # prod postgres limit
SHM="${BENCH_SHM:-256m}"                      # shm_size in docker-compose.prod.yml
SB="${BENCH_SHARED_BUFFERS:-128MB}"           # prod setting
CPUSET="${BENCH_CPUSET:-}"                    # e.g. 2,3: two physical cores, like 2 vCPUs

retry() {
  for _ in $(seq 120); do "$@" >/dev/null 2>&1 && return; sleep 1; done
  docker logs --tail 20 "$NAME" >&2
  echo "timed out waiting for: $*" >&2
  exit 1
}
wait_pg() {
  retry docker exec "$NAME" pg_isready -U honeywatch
  sleep 2
  retry docker exec "$NAME" psql -U honeywatch -d postgres -tAc 'select 1'
}
psqlb() { docker exec -i "$NAME" psql -q -U honeywatch -d honeywatch "$@"; }

case "${1:-}" in
  up)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    mkdir -p "$DATA"
    # Loopback only: the database holds unredacted attacker data behind a known password.
    # :z relabels the bind mount for SELinux hosts and is a no-op elsewhere.
    docker run -d --name "$NAME" --shm-size="$SHM" --memory="$MEM" --memory-swap="$MEM" \
      --cpus="$CPUS" ${CPUSET:+--cpuset-cpus="$CPUSET"} \
      -e POSTGRES_USER=honeywatch -e POSTGRES_PASSWORD=bench -e POSTGRES_DB=postgres \
      -p "127.0.0.1:$PORT:5432" -v "$DATA:/var/lib/postgresql/data:z" "$IMAGE" \
      postgres -c random_page_cost=1.1 -c "shared_buffers=$SB" \
      -c shared_preload_libraries=pg_stat_statements -c track_io_timing=on >/dev/null
    wait_pg
    echo "up: $NAME mem=$MEM cpus=$CPUS shm=$SHM shared_buffers=$SB cpuset=${CPUSET:-none}" ;;
  restore)
    [ -f "$DUMP" ] || { echo "no dump at $DUMP (set BENCH_DUMP)"; exit 1; }
    if [ "$(docker exec "$NAME" psql -U honeywatch -d postgres -tAc \
        "select count(*) from pg_database where datname='honeywatch'")" != 0 ]; then
      echo "already restored; run 'bench.sh down' first to start over"; exit 0
    fi
    errors=$(gzip -dc "$DUMP" | docker exec -i "$NAME" psql -q -U honeywatch -d postgres 2>&1 \
      | grep -c ERROR || true)
    echo "restore: $errors errors (two are expected: role honeywatch exists, current user cannot be dropped)"
    psqlb -tAc "select 'sessions '||count(*) from sessions" ;;
  prepare)
    psqlb -c "ALTER ROLE honeywatch PASSWORD 'bench'" \
          -c "ALTER ROLE honeywatch_ingestor PASSWORD 'bench'" \
          -c "ALTER ROLE honeywatch_api PASSWORD 'bench'" >/dev/null
    echo "prepare: alembic from $API_DIR"
    (cd "$API_DIR" && eval "$("$SELF" env)" && uv run alembic upgrade head)
    # pg_stat_statements counts layout builds without instrumenting a released image.
    psqlb -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements" >/dev/null
    psqlb -c "VACUUM ANALYZE" ;;
  restart) docker restart "$NAME" >/dev/null; wait_pg ;;
  env) cat <<ENV
export BENCH_NAME=$NAME POSTGRES_HOST=localhost POSTGRES_PORT=$PORT POSTGRES_USER=honeywatch POSTGRES_PASSWORD=bench POSTGRES_DB=honeywatch ENVIRONMENT=development PYTHONPATH=.
ENV
  ;;
  psql) shift; psqlb "$@" ;;
  status)
    docker inspect "$NAME" --format \
      'mem={{.HostConfig.Memory}} nanocpus={{.HostConfig.NanoCpus}} shm={{.HostConfig.ShmSize}} cpuset={{.HostConfig.CpusetCpus}}'
    psqlb -tAc "select 'alembic '||version_num from alembic_version" \
          -c "select 'sessions '||count(*)||', ssh_clients '||(select count(*) from ssh_clients) from sessions" \
          -c "show shared_buffers" -c "show max_parallel_workers_per_gather"
    psqlb -tAc "select 'pgss '||count(*) from pg_stat_statements" 2>/dev/null \
      || echo "pg_stat_statements unavailable (run prepare)" ;;
  down)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    # The data directory belongs to the container's postgres uid: empty it from inside one.
    [ -d "$DATA" ] && docker run --rm -v "$DATA:/d:z" "$IMAGE" sh -c 'rm -rf /d/* /d/.[!.]*' \
      && rmdir "$DATA" || true
    echo "down: container and data removed" ;;
  *) sed -n 2,19p "$0"; exit 1 ;;
esac
