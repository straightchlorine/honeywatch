---
description: "Deploy Honeywatch on a VPS with Docker Compose, pin every port to loopback, and verify it before exposing anything."
---

# Deploy the Stack

This page takes you from an empty machine to a running honeypot with nothing
published to the internet yet. Opening port 22 and reaching the dashboard from
your laptop are separate pages, because both can lock you out if done in the
wrong order.

<div class="grid cards" markdown>

-   :material-docker:{ .lg .middle } **Deploy the Stack**

    ---

    Clone, configure, pin the ports, bring the containers up.

    [Start here](#what-you-need)

-   :material-shield-alert:{ .lg .middle } **Exposing Port 22**

    ---

    Move your real SSH server off 22, confirm you can still get in, then hand
    the port to Cowrie.

    [Exposing Port 22](exposing.md)

-   :material-laptop:{ .lg .middle } **Watching It Remotely**

    ---

    Read the dashboard from your laptop over an SSH tunnel instead of
    publishing it.

    [Watching It Remotely](remote-access.md)

-   :material-wrench:{ .lg .middle } **Operating It**

    ---

    Logs, updates, geolocation refresh, backups.

    [Operating It](operations.md)

</div>

!!! danger "This is a real honeypot"
    Once port 22 is reachable it will be attacked continuously, usually within
    minutes. Run it on a machine you are willing to wipe.

    You will also be storing other people's usernames, passwords, commands and
    uploaded binaries. Whether you may keep that, and for how long, depends on
    where you are.

## What You Need

| Requirement | Notes |
|---|---|
| A machine you can rebuild | A small VPS or a spare box. |
| Docker Engine with Compose v2.24.4 or newer | The `!override` merge tag used below needs it. Check with `docker compose version`. |
| `git` | To clone the repo. |
| Root or `sudo` | For `docker compose`, and later to move your SSH server. On a box you are deliberately exposing, prefer `sudo docker compose` over joining the `docker` group, which is root-equivalent. |

`just`, `uv` and `pnpm` appear in the repo but are contributor tools. You do
not need them.

No minimum spec has been measured. The heaviest moment is the first build,
which compiles the Vue dashboard on the box, so a very small machine fails
there first.

## Which Compose File

Use `docker-compose.yml`. The other file, `docker-compose.prod.yml`, is the
maintainer's own deployment: it has no dashboard service, pulls prebuilt
images by version tag, and refuses to start without an address on a private
network you do not have. `docker-compose.yml` builds from the source you
cloned and includes everything.

## Clone and Configure

```bash
git clone https://github.com/straightchlorine/honeywatch.git
cd honeywatch
cp .env.example .env
```

Replace both `changeme` values in `.env` with something generated:

```bash
openssl rand -hex 32   # POSTGRES_PASSWORD
openssl rand -hex 32   # FLASK_SECRET_KEY
```

The API refuses to boot without a real `FLASK_SECRET_KEY`, and you will see
that as gunicorn workers dying in a loop rather than a clear error.

The rest of `.env.example` can stay as it is. The MaxMind variables are
optional, and everything else belongs to the production file. See
[Configuration](../getting-started/configuration.md).

## Pin the Ports Before the First Start

`docker-compose.yml` publishes four ports, and none of them names an interface,
so all four bind `0.0.0.0`:

| Service | Default | On a VPS this means |
|---|---|---|
| cowrie | `2222:2222` | Fine to expose, but on the wrong port |
| postgres | `5433:5432` | A superuser database on the internet |
| api | `5000:5000` | An unauthenticated API on the internet |
| dashboard | `8080:80` | Your whole dataset, public |

Fix it with a `docker-compose.override.yml` next to the compose file. Compose
picks that name up automatically.

!!! warning "Overrides append to `ports:` unless you say otherwise"
    Compose merges port lists. Without a merge tag, `127.0.0.1:8080:80` is
    added next to the original `0.0.0.0:8080`, and the container then fails
    to start with `address already in use` because both want host port 8080.
    Give Cowrie a second port the same way and it comes up on both. Write
    `ports: !override` so the list is replaced, and check the result with
    `docker compose config`.

```yaml title="docker-compose.override.yml"
services:
  cowrie:
    ports: !override
      - "127.0.0.1:2222:2222"

  api:
    ports: !override
      - "127.0.0.1:5000:5000"

  dashboard:
    ports: !override
      - "127.0.0.1:8080:80"

  postgres:
    ports: !override
      - "127.0.0.1:5433:5432"
```

Cowrie stays on loopback for now. [Exposing Port 22](exposing.md) changes that
one line to `"22:2222"` once your real SSH server is out of the way.

Postgres keeps a loopback mapping because the repo's host-side helpers connect
to `localhost:5433`. If you will never run those, `ports: !override []`
removes it entirely.

Now check:

```bash
docker compose config
```

Each of the four services should show exactly one `ports:` entry with
`host_ip: 127.0.0.1`. Two entries means the tag is missing. An entry with no
`host_ip` at all is still public.

## Start It

```bash
docker compose up -d --build
```

This builds the ingestor, API and dashboard from source and pulls Cowrie and
Postgres. The first run takes a while. A one-shot `api-migrate` container
creates the schema before the API and ingestor start, and re-runs on every
`up`, so there is no separate migration step.

## Verify Before Exposing Anything

```bash
docker compose ps
```

`api-migrate` shows as exited with code 0; that is correct. Four of the five
long-running containers report health; Cowrie has no healthcheck in this file.
Then check the API:

```bash
curl -s 127.0.0.1:5000/health          # {"status": "ok"}, never touches the database
curl -s -i 127.0.0.1:5000/health/ready # 200 if the database answers, 503 if not
```

Put a real session through the pipeline. Cowrie only accepts credentials on its
allowlist, so use one:

```bash
ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@127.0.0.1
# password: changeme
```

Type a command, `exit`, then:

```bash
curl -s 127.0.0.1:5000/api/v1/stats/totals
```

The session count should be 1. Loopback sessions count because
`docker-compose.yml` sets `DROP_LOOPBACK: "0"`.

To see the session in the dashboard you need a tunnel, which is
[Watching It Remotely](remote-access.md). Do not publish 8080 to check.

At this point all four ports are on `127.0.0.1` and nothing is reachable from
outside. That is the state you want before continuing.

## What This File Does Not Do

`docker-compose.yml` is the development file. It builds from source and has a
dashboard, which is why it is the right base, but it is not hardened:

- **No separate database roles.** The API and the ingestor both connect as the
  superuser. The production file creates a read-only role for the API.
- **No outbound restrictions on Cowrie.** The production file forces the
  honeypot through a proxy that only allows DNS, 80 and 443. Here Cowrie has
  ordinary outbound access.
- **No container hardening.** No read-only root, no dropped capabilities, no
  memory or CPU limits.
- **No rate limiting on the API.** Another reason to keep 5000 on loopback.
- **No log rotation.** Cowrie's JSON log and Docker's container logs both grow
  without bound.
- **No named volume for Cowrie's state.** Host keys and captured samples live
  in an anonymous volume the image declares. They survive `docker compose up`
  recreating the container, but `docker compose down` discards them. The
  hashes in Postgres survive either way.

All of these can be added to the same override file. `environment:` merges
by variable name and `volumes:` by container path, so those replace cleanly
without a tag; only `ports:` needs `!override`.

## Next

<div class="grid cards" markdown>

-   :material-shield-alert:{ .lg .middle } **Exposing Port 22**

    ---

    Move sshd, prove you can still log in, then give port 22 to Cowrie.

    [Exposing Port 22](exposing.md)

-   :material-laptop:{ .lg .middle } **Watching It Remotely**

    ---

    Forward port 8080 over SSH and read the dashboard from your laptop.

    [Watching It Remotely](remote-access.md)

</div>
