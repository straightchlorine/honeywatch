---
description: "Logs, updates, GeoLite2 refresh, backups, pruning and metrics for a running Honeywatch honeypot."
---

# Operating It

Reading the logs, updating without losing the schema, keeping geolocation
current, backups, and what grows on disk. Everything here assumes the compose
stack from [Deploy the Stack](index.md), run from the repository root.

Commands that use `$POSTGRES_USER` or `$POSTGRES_DB` need `.env` loaded into
your shell first; Compose reads it, your shell does not:

```bash
set -a; . ./.env; set +a
```

## Watching the Pipeline

| Command | Shows |
|---|---|
| `docker compose logs -f api ingestor` | Startup, errors, write failures |
| `docker compose exec ingestor tail -f /logs/cowrie.json` | Raw Cowrie events, as the ingestor reads them |
| `docker compose logs -f cowrie` | Cowrie's own startup and connection chatter |

`just logs api ingestor` and `just cowrie-log` are shorthands for the first
two.

The middle one is the one that matters. If an attack shows up in `cowrie.json`
but not on the dashboard, the problem is the ingestor or the database. If it
is not in `cowrie.json` either, the problem is Cowrie.

`docker compose ps` shows health for four of the five containers:

| Service | Check | Interval |
|---|---|---|
| `postgres` | `pg_isready` | 5s |
| `api` | GET `/health` | 30s |
| `ingestor` | `/tmp/healthy` touched in the last 60s | 30s |
| `dashboard` | GET `/` | 15s |
| `cowrie` | none | |

!!! warning "A healthy API is not a working API"
    `/health` returns a static `ok` and never touches the database, so a dead
    Postgres does not restart the API. `/health/ready` runs a real query and
    returns 503 when the database is unreachable. Use that one to find out
    whether data is being served.

## Updating

The stack builds from your checkout, so an update is a pull and a rebuild:

```bash
git pull
docker compose up -d --build
```

`api-migrate` runs on every `up` and brings the schema to whatever the new
code expects before the API and ingestor restart.

`docker compose up -d --build` rebuilds the api, ingestor and dashboard but
does not re-fetch Cowrie or Postgres. `cowrie/cowrie` is pinned to a specific
tag in `docker-compose.yml`. To move it, change the `image:` line and run
`docker compose up -d cowrie`, then watch `docker compose logs ingestor` for
`parser: dropped event id=...`, which means an upstream release changed an
event shape.

Take a backup before an update that includes migrations. There is no
automated rollback.

## Refreshing Geolocation

MaxMind publishes new GeoLite2 builds regularly. The files live in
`ingestor/data/`:

```bash
just fetch-mmdb              # or: set -a; . ./.env; set +a; ./scripts/fetch-mmdb.sh ingestor/data
docker compose restart ingestor
```

The restart matters. The ingestor opens each `.mmdb` on its first lookup and
holds it open, so a running ingestor keeps using the old file.

New databases only affect new sessions. To re-look-up every IP already in the
database:

```bash
docker compose exec ingestor python -m src.reclassify_geoip            # all
docker compose exec ingestor python -m src.reclassify_geoip --ip 1.2.3.4
```

It is idempotent and safe while the ingestor is live. Enrichment otherwise
happens only when a session connects, and a repeat visitor is not re-written
within an hour, so restarting the ingestor alone changes nothing for rows
already in the database.

## Backups

Everything the dashboard shows lives in Postgres. Dump the whole cluster:

```bash
docker compose exec -T postgres pg_dumpall -U "$POSTGRES_USER" \
  | gzip > "honeywatch-$(date +%F).sql.gz"
```

`just db restore <file>` replays that format: it stops the API and ingestor,
drops and recreates the schema, replays only the `honeywatch` database
section (skipping the role and grant statements that would lock the services
out), and starts them again. It refuses a file with no `\connect` marker
before touching anything, so handing it a `pg_dump` file is an error, not a
wipe.

Without `just`, take a plain `pg_dump` instead and replay it by hand. This
wipes the current data before reading the dump, so `gzip -t` the archive
first:

```bash
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip > honeywatch.sql.gz

docker compose stop api ingestor
docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "DROP SCHEMA IF EXISTS public CASCADE" -c "CREATE SCHEMA public"
gzip -dc honeywatch.sql.gz \
  | docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 \
      -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose start api ingestor
```

Test a restore into a throwaway stack before you need one.

## Pruning

Nothing enforces retention. Two things grow for as long as the honeypot runs.

**The database.** Every child table cascades from `sessions`, so one statement
clears everything hanging off old sessions:

```sql
DELETE FROM sessions WHERE started_at < NOW() - INTERVAL '90 days';
```

`geo_locations` is keyed on IP rather than session and survives the prune,
which is what you want since the same IPs come back. `just db shell` opens
`psql`. Back up first!

**`cowrie.json`.** The repo configures no rotation for it, in either compose
file. Check the size with:

```bash
docker compose exec ingestor ls -lh /logs/cowrie.json
```

Rotation is your call, and it has a catch: the ingestor keeps no offset and
seeks to the end of the file whenever it opens one. While it is running, it
notices a rotation and reopens the new file, but from the end, so anything
written in the window before the reopen is skipped. While it is stopped,
anything rotated away is gone. Truncation in place it handles properly.
Whatever you choose, do it while the ingestor is up.

Docker's own container logs are also uncapped on this compose file:

```bash
sudo du -sh /var/lib/docker/containers/*/*-json.log
```

## How the Ingestor Behaves Under Outages

| Behavior | Detail |
|---|---|
| Starts at EOF | No stored offset. A restart never replays history. |
| Bounded queue | 10000 lines between the tailer and the writer. When full, the tailer blocks. |
| Retries | 3 attempts per write, sleeping 1s then 2s. |
| Circuit breaker | 50 consecutive failures trip it. It then sleeps 30s, probes, and doubles the wait after each failed probe up to 5 minutes. |
| Stays healthy while tripped | The liveness file keeps being touched, so the container does not restart mid-backlog. |
| Oversized lines | Over 1 MiB is dropped. |

During a database outage the queue fills, the tailer blocks, and Cowrie keeps
appending to `cowrie.json`. When Postgres returns, the ingestor works through
the queue and then the file. You lose only what was in memory if the container
is killed.

## Optional: Prometheus Metrics

Off by default, and neither compose file passes the variable. Add it to your
override:

```yaml
services:
  ingestor:
    environment:
      METRICS_ENABLED: "1"
```

The server listens on `127.0.0.1:9101` inside the container, so a `ports:`
entry does nothing. Scraping it means a sidecar in the same network namespace.

| Metric | Meaning |
|---|---|
| `ingestor_events_processed_total{outcome}` | Events processed, by outcome |
| `ingestor_events_dropped_total{reason}` | Events dropped without being persisted |
| `ingestor_parser_drift_total{eventid}` | Cowrie events that failed to parse |
| `ingestor_orphan_event_total{kind}` | Child events whose session `connect` was missed |
| `ingestor_geo_upsert_failures_total` | Geo enrichment failures |
| `ingestor_fuse_blown_total` | Times the circuit breaker tripped |
| `ingestor_queue_depth` | Current queue depth |
| `ingestor_consecutive_failures` | Write failures since the last success |
| `ingestor_fuse_open` | 1 while tripped |

The labelled counters only appear once an event with that label has been
seen, so a freshly started ingestor shows the gauges and little else.

`ingestor_parser_drift_total` is the one to watch after an update. A non-zero
rate on a previously quiet event id means Cowrie changed a field shape.
