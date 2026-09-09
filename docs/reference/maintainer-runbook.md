---
description: "How the public Honeywatch instance is released, rolled back and operated. Not a deployment guide."
---

# Operating This Instance

!!! info "This is not a deployment guide"
    This page records how one specific public instance is operated. If you are
    deploying honeywatch, the [Self-Hosting](../self-hosting/index.md) section
    is the path, and nothing here is required.

## Scope

The instance runs `docker-compose.prod.yml` on a single VPS at
`/opt/honeywatch`, with the `api` and `ingestor` images pulled from GHCR.
`egress-proxy` is built on the box from `cowrie/egress-proxy`, so
`docker compose pull` never refreshes it and a rollback never touches it.

That file requires `API_VERSION`, `INGESTOR_VERSION`, `TS_IP`,
`POSTGRES_INGESTOR_PASSWORD` and `POSTGRES_API_PASSWORD`, and has no dashboard
service. The dashboard is served from elsewhere and is out of scope here.

## Release Flow

A release is a `v*.*.*` tag on a `master` commit:

```bash
just bump-version v0.7.2
git push origin master
git tag v0.7.2 && git push origin v0.7.2
```

`release.yml` then runs, in order:

| Job | What it does |
|---|---|
| `verify-tag` | Fails unless the tag is contained in `origin/master` |
| `build-and-push` | Builds `api`, `ingestor` and `dashboard`, pushes to GHCR and Docker Hub |
| `attestation` | SPDX SBOM, build provenance, keyless cosign signature via OIDC |
| `rollout` | Joins the tailnet, SSHes to the honeypot, updates the stack, verifies each image's signature by digest |
| `release` | `gh release create --generate-notes` |

The rollout strips the leading `v` and runs on the honeypot:

```bash
cd /opt/honeywatch
export API_VERSION='0.7.2' INGESTOR_VERSION='0.7.2'
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

That `up` runs the migration: `api` and `ingestor` depend on `api-migrate`
completing successfully. Only the api and ingestor images are deployed; the
dashboard is built and signed but not rolled out, and Cowrie is a pinned
upstream image untouched by releases.

!!! warning "Rollout is fire-and-forget"
    No remote health probe, no automatic rollback. A hard startup failure
    surfaces as a non-zero SSH step, because `proxy` waits for `api` to be
    healthy and `api` waits for `api-migrate`. A tag that starts cleanly but
    serves wrong data does not. Green means "the images started".

Two release workflows serialize (`concurrency: group: release`). Manual
rollback bypasses the workflow, so nothing serializes that.

## Manual Rollback

```bash
ssh honeypot   # your own ~/.ssh/config Host block, port 2022, not 22
cd /opt/honeywatch
# Pick a known-good tag: gh release list -L 20 from your laptop.
export API_VERSION=0.7.0 INGESTOR_VERSION=0.7.0
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --no-deps api ingestor proxy
```

!!! danger "Image tags have no leading v"
    The release tag is `v0.7.0`; the image tag is `0.7.0`. Pasting the release
    tag gives a `pull` that 404s.

`--no-deps` with the explicit service list is the point: it keeps
`api-migrate` from running. See below.

## Migration Policy

Nothing in the api image runs migrations; its entrypoint is gunicorn. The only
thing that calls alembic in production is the one-shot `api-migrate` service,
which reuses the api image with `entrypoint: ["alembic", "upgrade", "head"]`.
`api` and `ingestor` are gated on it with `service_completed_successfully`.
`api-migrate` connects as `POSTGRES_USER` because it needs DDL rights; `api`
and `ingestor` use the least-privilege roles.

!!! warning "A rollback must not re-run api-migrate"
    An older image's `alembic/versions/` lacks the newer revision, so
    `alembic upgrade head` errors, and the gate then blocks `api` and
    `ingestor` from starting forever. A rollback becomes an outage.

Hence the rule: every production migration stays backwards compatible with
the previous release. Additive DDL only, no `DROP`, no incompatible type
change. A rollback then leaves the schema ahead of the code without breaking
it.

If a migration must be undone, run the downgrade from the **new** image, which
is the only one with both revisions on disk, then swap:

```bash
cd /opt/honeywatch
API_VERSION=<broken-version> docker compose -f docker-compose.prod.yml \
  run --rm --no-deps --entrypoint alembic api-migrate downgrade <prev-revision-id>
export API_VERSION=<prev-version> INGESTOR_VERSION=<prev-version>
docker compose -f docker-compose.prod.yml up -d --no-deps api ingestor proxy
```

`--entrypoint alembic` is required. `docker compose run` replaces the
service's `command`, not its `entrypoint`, so without the flag the container
runs `alembic upgrade head alembic downgrade <rev>`.

Find `<prev-revision-id>` with `git show <prev-tag>:api/alembic/versions/`.

## Postgres Networking

Postgres sits on the `backend` bridge, declared `internal: true`, reachable
only by service name from `api-migrate`, `api`, `ingestor` and `proxy`. No
host port, no tailnet exposure, no server-side TLS; every client connects
`sslmode=disable` on the isolated bridge.

`pg_hba.conf` is mounted and enforced with `-c hba_file=...`. Over TCP it
permits only `172.16.0.0/12` and rejects everything else. The unix socket is
`trust`, which is what lets the initdb scripts bootstrap roles.

!!! note "Historical: the removed tailnet exposure"
    An earlier design exposed Postgres on the tailnet with a read-only
    LISTEN/NOTIFY role behind self-signed TLS, meant to feed a live SSE
    stream. That consumer was never built, so all of it was removed. The
    dashboard polls.

## Re-applying Postgres Roles

`postgres/init.sh` runs only on a fresh data directory. An existing volume
will not pick up role changes after a pull. Apply them with the idempotent
`postgres/upgrade-roles.sql`, which also backfills grants on existing tables:

```bash
ssh honeypot
cd /opt/honeywatch
set -a; . ./.env; set +a
docker cp postgres/upgrade-roles.sql honeywatch-db:/tmp/upgrade-roles.sql
docker compose -f docker-compose.prod.yml exec -e PGPASSWORD="$POSTGRES_PASSWORD" \
  postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v INGESTOR_PW="$POSTGRES_INGESTOR_PASSWORD" \
  -v API_PW="$POSTGRES_API_PASSWORD" \
  -f /tmp/upgrade-roles.sql
```

Sourcing `.env` is the step people skip. Without it the shell expands every
variable to empty and the script runs as `psql -U '' -d ''`.

## Reading a Failed Release

| Failure | Meaning | Action |
|---|---|---|
| `verify-tag` | Tag is not on `master` | Delete the tag, merge, re-cut |
| `build-and-push` or `attestation` | Nothing deployed | Fix and re-cut; the honeypot is untouched |
| `rollout` SSH or tailnet | Connectivity flake | Re-run; the commands are idempotent |
| `rollout` cosign verify | Images are live but signatures did not verify | Investigate before trusting the deploy |
| Green, but stack unhealthy | The pipeline probes nothing | `ssh honeypot`, then `docker compose -f docker-compose.prod.yml ps` and `logs -f api ingestor` |

`api` and `ingestor` stuck in `Created` almost always means `api-migrate`
exited non-zero. Read `docker compose -f docker-compose.prod.yml logs
api-migrate` first.

Container health is not a data-path signal: the healthcheck hits `/health`,
which never touches the database. Use `/health/ready`.
