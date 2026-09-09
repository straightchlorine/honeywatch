---
description: "Bring the Honeywatch stack up on your laptop with Docker Compose and see your first honeypot session in the dashboard."
---

# Quick Start

This gets the whole stack running on your own machine: Cowrie on port 2222, the
ingestor, PostgreSQL, the API and the dashboard. It is the shortest path to a
working dashboard, **not a production setup**.

!!! warning "Local development only"
    `docker-compose.yml` publishes every port on all interfaces, PostgreSQL
    included. Run this behind a firewall. For a VPS, follow
    [Deploy the Stack](../self-hosting/index.md) instead.

## Prerequisites

Docker Engine with the Compose v2 plugin, and git.

`just`, `uv` and `pnpm` show up throughout the repo, but they are contributor
tools. Every `just` recipe used here is a thin wrapper, and the plain Docker
command is shown alongside it.

## Bring the Stack Up

```bash
git clone https://github.com/straightchlorine/honeywatch.git
cd honeywatch
cp .env.example .env
```

Open `.env` and replace the two `changeme` values:

| Variable | What it is |
|----------|------------|
| `POSTGRES_PASSWORD` | Password for the database role the API and ingestor use |
| `FLASK_SECRET_KEY` | Flask session secret; the API refuses to start without one |

Everything else in the file can stay as it is. The MaxMind variables are only
needed for [geolocation](#optional-geolocation), and the rest belong to the
maintainer's production compose file. See [Configuration](configuration.md)
for the full list.

Now build and start everything:

```bash
docker compose up -d --build   # just dev
```

The first build takes a few minutes because it compiles the Vue dashboard. When
it finishes, `docker compose ps` should show five containers running:
`honeywatch-cowrie`, `honeywatch-db`, `honeywatch-ingestor`, `honeywatch-api`
and `honeywatch-dashboard`. A sixth, `honeywatch-api-migrate`, runs once to
create the schema and exits; it does that on every `up`, so the database is
always at the current version.

Check that the API answers:

```bash
curl -s http://localhost:5000/api/v1/stats/totals
```

You should get a JSON object of zeroes. Zeroes are correct at this point.

## Generate Some Traffic

SSH into your own honeypot:

```bash
ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@localhost
```

That is what `just attack` runs. The `-o` flags are there because Cowrie's host
key changes after every `docker compose down`.

Not every password works. `cowrie/userdb.txt` is an allowlist with a catch-all
reject at the end, so most guesses fail on purpose. Any of these gets you in:

| Username | Passwords |
|----------|-----------|
| `root` | `123456`, `123456789`, `admin`, `qwerty`, `abc123`, `letmein`, `changeme` |
| `admin` | `admin`, `admin123`, `password` |
| `centos` | `centos`, `centos123` |
| `pi` | `raspberry` |
| `postgres` | `postgres` |

`root:root`, `root:toor`, `root:12345` and `root:password` are rejected on
purpose. A box where the four most-guessed passwords all work looks like a
honeypot.

Once you are in, type a few commands (`uname -a`, `cat /etc/os-release`,
`wget http://example.com/x`), then `exit`. Within a second or two the session
shows up at <http://localhost:8080> on the Overview feed and under Sessions,
where you can read the transcript back.

To watch the raw events as the ingestor sees them:

```bash
docker compose exec ingestor tail -f /logs/cowrie.json   # just cowrie-log
```

Your own sessions are only counted because `docker-compose.yml` sets
`DROP_LOOPBACK: "0"`. By default the ingestor drops anything from 127.0.0.1.

## Where Things Listen

| Service | Address |
|---------|---------|
| Dashboard | <http://localhost:8080> |
| API | <http://localhost:5000> |
| Honeypot | `localhost:2222` |
| PostgreSQL | `localhost:5433` |

Swagger UI is at <http://localhost:5000/api/v1/swagger>, ReDoc at
<http://localhost:5000/api/v1/redoc>. Health probes sit at the root:
`/health` and `/health/ready`.

You only need port 8080 to use the dashboard. Its nginx proxies `/api/` to the
API container, so port 5000 is there for your own `curl`.

If 5433 is taken, set `POSTGRES_HOST_PORT` in `.env`.

## Optional: Geolocation

Without MaxMind databases everything still works: the ingestor logs
`GeoIP databases missing` once and stores sessions without country, city or
ASN. The world map and the Origins page then have nothing to draw.

To turn it on, create a free MaxMind GeoLite2 account and put the credentials
in `.env`:

```ini
MAXMIND_ACCOUNT_ID=...
MAXMIND_LICENSE_KEY=...
```

Then download the databases and restart the ingestor:

```bash
just fetch-mmdb
docker compose restart ingestor
```

The script only reads its environment, and `just` is what loads `.env` into it.
Without `just`:

```bash
set -a; . ./.env; set +a
./scripts/fetch-mmdb.sh ingestor/data
docker compose restart ingestor
```

The files land in `ingestor/data/`, which is bind-mounted into the container.
The ingestor opens them on the first lookup and holds them open, that's why the
restart.

Sessions recorded before this point stay unenriched. To backfill them:

```bash
docker compose exec ingestor python -m src.reclassify_geoip
```

Add `--ip <address>` for a single address. It is safe to rerun while the
ingestor is live.

## Optional: Synthetic Data

An empty dashboard is hard to judge. `just seed` fills the database with
realistic fake traffic (about 17,000 sessions over the last week from 733
addresses), and `just seed-live` drips a few new sessions every 15 seconds so
the Overview feed and the map keep moving.

```bash
just seed        # wipes, then populates
just seed-live   # appends, ctrl-c to stop
```

!!! warning "just seed destroys existing data"
    It truncates every table before inserting. `just seed-live` is append-only.

Both run on the host and need `just` and `uv`. See
[Development](../reference/development.md).

## Stopping and Resetting

```bash
docker compose down     # just down
```

This keeps the `cowrie-logs` and `postgres-data` volumes, so your data survives
the next `up`.

To throw the data away as well:

```bash
docker compose down -v
```

The next `up` starts with an empty database.

## Next

You have a honeypot only you can reach. To catch real traffic, read
[Deploy the Stack](../self-hosting/index.md), then
[Exposing Port 22](../self-hosting/exposing.md). If something above did not
behave, start at [Troubleshooting](../reference/troubleshooting.md).
