---
description: "Every environment variable Honeywatch reads, what reads it, its default, and what breaks when it is wrong."
---

# Configuration

Everything is configured through a single `.env` file at the repository root,
plus the files Cowrie reads directly. This page lists every variable, what reads
it, and what it falls back to.

## The .env File

```bash
cp .env.example .env
```

Docker Compose reads `.env` from the directory it runs in, and the `justfile`
loads it too, so both see the same values. Four variables must be set before
the stack runs: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` and
`FLASK_SECRET_KEY`. The example ships `changeme` for the two secrets.

!!! warning "A variable only reaches a container if the compose file passes it"
    Each service in `docker-compose.yml` lists what it receives under
    `environment:`. Adding a name to `.env` that is not in that list does
    nothing. The tables below say which variables are already wired in.

Changes take effect when the container is recreated with `docker compose up -d`.
Volumes and the schema survive that.

## Database

| Variable | Read by | Default | Notes |
|---|---|---|---|
| `POSTGRES_USER` | postgres, api, ingestor | `honeywatch` | Required. Becomes the bootstrap superuser on first boot. In `docker-compose.yml` both the api and the ingestor connect as this role. |
| `POSTGRES_PASSWORD` | postgres, api, ingestor | none | Required. The api refuses to boot without it; the ingestor exits with `KeyError`. |
| `POSTGRES_DB` | postgres, api, ingestor | `honeywatch` | Required. |
| `POSTGRES_HOST` | api | `localhost` | The api defaults to localhost when running in development. |
| `POSTGRES_HOST` | ingestor | `postgres` | The ingestor defaults to the postgres service name in Docker. |
| `POSTGRES_PORT` | api, ingestor | `5432` | The port inside the Docker network, not the host port. |
| `POSTGRES_SSLMODE` | api | `disable` | Postgres is only reachable on the private bridge, so there is no certificate step. The ingestor has no knob for this. |
| `POSTGRES_HOST_PORT` | `docker-compose.yml` | `5433` | Changes the host-side publish only, never the bind address; for that see [Pin the Ports](../self-hosting/index.md#pin-the-ports-before-the-first-start). |

Postgres reads `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` only when
it initialises an empty data directory. Once `postgres-data` exists, editing them
in `.env` changes nothing on the server and breaks every service that reconnects
with the new values. Pick the names before the first `docker compose up`. To
change them later, alter the role and database by hand (`just db shell`), or
start over with `docker compose down -v`, which destroys your data.

The `pg_hba.conf` warning at the top of `.env.example` applies to
`docker-compose.prod.yml`, which mounts that file. `docker-compose.yml` does
not, so on the self-hosting path the names are yours to choose.

## API

| Variable | Read by | Default | Notes |
|---|---|---|---|
| `ENVIRONMENT` | api | `production` | Only `development` and `production` are accepted. `docker-compose.yml` does not set it, so it falls back to `production`.  |
| `FLASK_SECRET_KEY` | api | none | Required. `ENVIRONMENT=development` enables an insecure fallback. |
| `LOG_LEVEL` | api | `INFO` | Not passed by the compose file. |
| `LOG_FORMAT` | api | `json` in production, `text` otherwise | Not passed by the compose file. |
| `GUNICORN_WORKERS` | api | `2` | Not passed by the compose file. |
| `GUNICORN_THREADS` | api | `4` | |
| `GUNICORN_TIMEOUT` | api | `30` | Seconds. |
| `GUNICORN_GRACEFUL_TIMEOUT` | api | `30` | Seconds. |

!!! warning "The API refuses to start without `FLASK_SECRET_KEY`"
    An empty secret makes the app factory raise at worker boot, which looks
    like gunicorn workers dying in a loop. Check `docker compose logs api`.
    The secret is checked before the database password, so fixing one can
    surface the other.

Two things are not configurable. Gunicorn binds `0.0.0.0:5000` inside the
container; the published host port is a compose setting. And the SQLAlchemy
pool is fixed at 5 connections plus 5 overflow, so keep
`GUNICORN_WORKERS * GUNICORN_THREADS` at or below 10.

## Geolocation

Optional. Without it the stack runs, but sessions have no country, city or ASN
and the world map and Origins page stay empty.

| Variable | Read by | Default | Notes |
|---|---|---|---|
| `MAXMIND_ACCOUNT_ID` | `scripts/fetch-mmdb.sh` | none | Only needed to download the databases. |
| `MAXMIND_LICENSE_KEY` | `scripts/fetch-mmdb.sh` | none | Same. |
| `GEOIP_DATA_DIR` | ingestor | `/data/geoip` | Not passed by the compose file, which bind-mounts `./ingestor/data` there. |

The ingestor expects `GeoLite2-City.mmdb` and `GeoLite2-ASN.mmdb` in that
directory. The [Quick Start](quick-start.md#optional-geolocation) covers
fetching them and backfilling old sessions.

!!! warning "`just reclassify-geoip` runs on the host"
    It needs `uv`, the Postgres host port, and `GEOIP_DATA_DIR` pointing at the
    real directory, otherwise it looks for `/data/geoip` on your host, finds
    nothing, and reports every address as unenrichable. Prefer
    `docker compose exec ingestor python -m src.reclassify_geoip`.

## Dashboard

| Variable | Read by | Default | Notes |
|---|---|---|---|
| `VITE_API_BASE` | dashboard, at build time | `/` (same origin) | Lives in `dashboard/.env.example`, not the root `.env`. Must be `/`, empty, or an absolute `http(s)://` URL. |

The Dockerfile declares no build argument for it, so the image compose builds
is always same-origin. It exists for `pnpm dev` against a separately running
API. Leave it empty everywhere else: the API sends no CORS headers and the
dashboard's CSP sets `connect-src 'self'`, so a cross-origin value is blocked
by the browser.

## Ingestor Tuning

| Variable | Read by | Default | Notes |
|---|---|---|---|
| `LOG_PATH` | ingestor | `/logs/cowrie.json` | The Cowrie log inside the shared volume. |
| `DROP_LOOPBACK` | ingestor | `1` | Drops sessions from loopback addresses. `docker-compose.yml` sets `0` so your own test logins count. |
| `RETRY_ATTEMPTS` | ingestor | `3` | Attempts per failed database write. |
| `RETRY_INITIAL_BACKOFF` | ingestor | `1.0` | Seconds, doubling between attempts. Three attempts take about three seconds. |
| `FUSE_THRESHOLD` | ingestor | `50` | Consecutive failures before the circuit breaker trips. |
| `FUSE_SLEEP` | ingestor | `30.0` | Seconds to wait after tripping before probing again. |
| `QUEUE_MAX` | ingestor | `10000` | Queue depth between the tailer and the writer. When full, the tailer blocks and lines stay in `cowrie.json`. |
| `HEALTHCHECK_PATH` | ingestor | `/tmp/healthy` | Liveness file. The Dockerfile health check reads the same path, so change both or neither. |
| `METRICS_ENABLED` | ingestor | `0` | `1` serves Prometheus metrics on `127.0.0.1` inside the container. |
| `METRICS_PORT` | ingestor | `9101` | |

`docker-compose.yml` passes only `DROP_LOOPBACK`. To change anything else, add
it to the ingestor's `environment:` block. The metrics endpoint binds to
loopback inside the container, so nothing outside can scrape it without a
sidecar or `docker compose exec`.

## Cowrie

Cowrie takes no environment variables in `docker-compose.yml`. It is configured
by files bind-mounted read-only from `cowrie/`:

| File | Controls |
|---|---|
| `cowrie.cfg` | Hostname, prompt, SSH banner, offered ciphers, sensor name, kernel strings, log path. |
| `userdb.txt` | Which username and password pairs are accepted. |
| `fs/centos-stream10.pickle` | The fake filesystem tree, built from a real CentOS Stream 10 image. |
| `cmdoutput.json` | Canned output for some commands. |
| `honeyfs/` | Contents of readable files such as `/etc/os-release`. |
| `txtcmds/` | Static output for commands like `df`, `lscpu` and `top`. |

Edit on the host, then `docker compose restart cowrie`.

`userdb.txt` is an allowlist with a catch-all reject at the end, and it
explicitly rejects `root:root`, `root:toor`, `root:12345` and `root:password`.
A file added to `honeyfs/` only shows up if the same path also exists in the
filesystem pickle.

## Production-Only Variables

`.env.example` lists several variables that `docker-compose.yml` never uses.
They belong to `docker-compose.prod.yml`, the maintainer's file for one
specific instance, and you do not need them.

| Variable | Purpose |
|---|---|
| `API_VERSION`, `INGESTOR_VERSION` | Image tags for prebuilt images. Not in `.env.example`. |
| `TS_IP` | Private-network address the internal proxy binds to. |
| `POSTGRES_INGESTOR_PASSWORD`, `POSTGRES_API_PASSWORD` | Passwords for the per-app roles created by `postgres/init.sh`. |
| `COWRIE_HONEYPOT_INTERNET_FACING_IP` | Makes `ifconfig` inside the honeypot show a public address instead of the container's NAT address. Either unset or non-empty; an empty value blanks the field. |

On the `docker-compose.yml` path there is no per-role split: the api and the
ingestor both connect as the bootstrap superuser.
