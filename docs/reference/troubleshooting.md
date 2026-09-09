---
description: "Symptoms and fixes for the failures the Honeywatch stack actually produces."
---

# Troubleshooting

Every entry is a failure this stack actually produces. Three commands answer
most questions first:

| Command | Tells you |
|---|---|
| `docker compose ps` | What is running, exited or restarting |
| `docker compose logs <service>` | Why a container exited, what the ingestor is doing |
| `docker compose config` | The effective config after your override was merged, including the real port list |

## The Stack Will Not Start

### The api container exits with a secret key error

```text
RuntimeError: FLASK_SECRET_KEY is not set; refusing to start with the insecure default.
```

`ENVIRONMENT` defaults to `production`, and in production the API refuses to
boot without a real secret. Set one in `.env` and `docker compose up -d api`.
`POSTGRES_PASSWORD` is checked the same way, right after, so expect a second
near-identical failure if that is also empty.

On a throwaway machine `ENVIRONMENT=development` enables an insecure fallback.
Never on anything reachable from the internet.

### The api container exits with an invalid ENVIRONMENT error

Only `development` and `production` are accepted. Anything else raises.

### Port 22 is already allocated

Your real SSH server still owns it. Move it and verify the new port before
retrying. See [Exposing Port 22](../self-hosting/exposing.md).

## No Data in the Dashboard

### api and ingestor are stuck in Created

`docker compose up` ends with `service "api-migrate" didn't complete
successfully: exit 1`, and `docker compose ps -a` shows the migrate container
exited non-zero. Both services wait for it to succeed, so a failed migration
blocks them from starting. Read its log:

```bash
docker compose logs api-migrate
```

The usual cause is a wrong `POSTGRES_PASSWORD` against an existing volume; see
[Changing POSTGRES_PASSWORD](#changing-postgres_password-in-env-has-no-effect).
Fix it and `docker compose up -d` again.

### Local test sessions never appear

`DROP_LOOPBACK` defaults to `1`, which discards sessions from `127.0.0.0/8`
and `::1`. `docker-compose.yml` sets it to `0`, so this only bites if you
removed that or are running the production file. Set it to `0` and recreate
the ingestor, or connect from another machine.

### Sessions appear but their commands or logins are missing

`docker compose logs ingestor` shows `orphan cmd event for session_id=...`.
Every child row attaches to a session by Cowrie's session id, and if the
ingestor never saw the `session.connect` (it started mid-session, or the
connect was dropped as loopback) the children have nowhere to go.

Nothing recovers them. The ingestor starts at the end of the log and keeps no
offset, so expect a few orphans after every restart. A steady stream of them
means the loopback drop above.

### Some Cowrie event types never show up

The ingestor handles a fixed set of event ids. `cowrie.command.success`,
`cowrie.command.failed`, `cowrie.session.file_upload` and a few others are
dropped by design, which is why there is no pass/fail metric on commands. An
event id the ingestor does not model at all is logged once at warning level
as `parser: dropped event id=...`.

### Every number is zero

Either nothing has attacked you yet, or the ingestor cannot write. Check:

```bash
docker compose logs --tail=50 ingestor
```

A healthy ingestor is quiet. Retry lines or `fuse blown` mean it cannot reach
Postgres; see [Database Problems](#database-problems). If it is clean, the
honeypot has not been found yet. A fresh port 22 usually sees its first scan
within minutes.

## Geolocation Is Missing

### The map and Origins pages are blank

Sessions are recorded, but no country or network appears anywhere. The
GeoLite2 files are missing. The ingestor logs this once, on the first lookup
from a public address:

```text
GeoIP databases missing at /data/geoip; geo enrichment disabled
```

Fetch them and restart:

```bash
just fetch-mmdb
docker compose restart ingestor
```

Without `just`, load `.env` first (`set -a; . ./.env; set +a`) and run
`./scripts/fetch-mmdb.sh ingestor/data`.

### Only recent sessions have a country

Enrichment happens at ingest time. Backfill the rest:

```bash
docker compose exec ingestor python -m src.reclassify_geoip
```

Run it again after any MaxMind update.

## Exposure and Access

### You cannot SSH to the host after handing over port 22

`ssh user@host` hangs, is refused, or lands you on a `[root@centos ~]#` shell
you do not recognise. That last one is Cowrie answering; you are inside the
honeypot. Connect on the port you moved sshd to. If you never verified that
port, use your provider's console to fix the config.

### A container fails to start with "address already in use" after adding the override

You bound the dashboard, API or Postgres to `127.0.0.1` in an override, and
`docker compose up` now reports `failed to bind host port 127.0.0.1:8080/tcp:
address already in use` (or 5000, or 5433) and the container is missing from
`docker compose ps`. Compose merges `ports:` lists by appending, so without a
tag the original `0.0.0.0` binding is still there and Docker cannot bind the
same host port twice. The same mistake on Cowrie does not error; it just
publishes Cowrie on both `2222` and whatever you added. Use `!override`:

```yaml
services:
  dashboard:
    ports: !override
      - "127.0.0.1:8080:80"
  postgres:
    ports: !override
      - "127.0.0.1:5433:5432"
```

Then `docker compose config` and count the entries under each `ports:`. One
per service, each with `host_ip: 127.0.0.1`. An entry with no `host_ip` at all
is still public.

### The tunnel connects but the page is blank

The forward target is wrong. Once the dashboard is on `127.0.0.1`, the tunnel
must terminate there, not on the public address:

```bash
ssh -p 2022 -N -L 8080:127.0.0.1:8080 user@your-server
```

### /health through the tunnel returns the dashboard HTML

The dashboard's nginx proxies only `/api/`. The health probes sit at the API
root, so forward 5000 too:

```bash
ssh -p 2022 -N -L 8080:127.0.0.1:8080 -L 5000:127.0.0.1:5000 user@your-server
curl -i http://localhost:5000/health/ready
```

## Database Problems

### The ingestor is healthy but nothing is written

Its log repeats retry lines and then `fuse blown: 50 consecutive failures,
sleeping 30s`. It has tripped its circuit breaker and stopped hammering the
database, while keeping its liveness file fresh so the container is not
restarted mid-backlog.

Fix the database and wait. It sleeps 30 seconds, probes, and doubles the
wait after each failed probe up to five minutes, then closes the breaker on
its own with `fuse: probe ok, closing`.
Cowrie keeps appending to its log meanwhile, so nothing is lost unless the
log is rotated before the ingestor catches up.

### Changing POSTGRES_PASSWORD in .env has no effect

Postgres applies its init variables only to a fresh data directory. Change it
inside the database, then update `.env` to match:

```bash
docker compose exec postgres psql -U honeywatch honeywatch \
  -c "ALTER ROLE honeywatch WITH PASSWORD 'your-new-password';"
docker compose up -d api ingestor
```

`docker compose down -v` also works, by deleting all your data.

### Postgres refuses connections after changing POSTGRES_USER

Same rule: the new role was never created because the data directory already
existed. Create it yourself or start from a fresh volume.

The `pg_hba.conf` warning in `.env.example` applies to `docker-compose.prod.yml`
only. The self-hosting file mounts no `pg_hba.conf`.

### database "honeywatch_test" does not exist

`just db test-init` creates it. It starts the postgres container itself if
needed.

## Development Checks

### just openapi-check fails

Either the API surface changed and the committed spec and client no longer
match, or you have uncommitted work in those paths; the recipe stages them and
diffs against the index, so it cannot pass while they are dirty.

```bash
just openapi-regen
git add api/openapi.json dashboard/src/api/generated
git commit -m "chore(api): regenerate openapi spec and client"
```

### CI fails where just test passed

`just test` skips `pnpm typecheck` and `pnpm e2e`. Run both before pushing:

```bash
just pnpm typecheck
just pnpm e2e
```
