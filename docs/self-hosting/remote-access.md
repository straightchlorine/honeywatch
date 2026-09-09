---
description: "Read the Honeywatch dashboard and API from your laptop over an SSH port forward without publishing them."
---

# Watching It Remotely

The honeypot needs to be on the internet. The dashboard, the API and the
database do not. Keep all three on loopback and reach them from your laptop
over an SSH port forward.

## Why Not Publish the Dashboard

The API has no authentication. Anyone who can reach port 5000 can read
everything you have captured, and there is no rate limiting in front of the
expensive aggregate queries. Postgres on 5433 is worse: on this compose file
both the API and the ingestor connect as the superuser.

The override file from [Deploy the Stack](index.md#pin-the-ports-before-the-first-start)
pins all of this to `127.0.0.1`. Check it took, from the host:

```bash
ss -ltn | grep -E '8080|5000|5433'
```

Every line should show `127.0.0.1` in the Local Address column. `0.0.0.0` or
`*` means the port is public.

## One Tunnel for the Dashboard

Forwarding one port is enough for the whole UI. The dashboard container runs
nginx, which serves the SPA and proxies `/api/` to the API container, and the
SPA calls the API same-origin.

```bash
ssh -p <your-ssh-port> -N -L 8080:127.0.0.1:8080 you@vps.example.com
```

Then open <http://localhost:8080>. `-N` holds the forward open without running
a command.

The forward target must be `127.0.0.1`, because that is where the container is
bound on the VPS.

## A Second Tunnel for the API

Forward 5000 as well if you want to hit the API directly:

```bash
ssh -p <your-ssh-port> -N \
    -L 8080:127.0.0.1:8080 \
    -L 5000:127.0.0.1:5000 \
    you@vps.example.com
```

```bash
curl -s localhost:5000/health
curl -s -i localhost:5000/health/ready
curl -s localhost:5000/api/v1/stats/totals
```

Three things need the 5000 forward rather than 8080:

- `/health` and `/health/ready` sit at the API root, not under `/api/`, so the
  dashboard's nginx does not proxy them.
- Swagger UI and ReDoc are under `/api/v1/`, but their `.js` and `.css` assets
  match nginx's static-file location before the `/api/` proxy, so they 404
  through 8080.

Forward 5433 for a `psql` session:

```bash
ssh -p <your-ssh-port> -N -L 5433:127.0.0.1:5433 you@vps.example.com
psql -h 127.0.0.1 -p 5433 -U "$POSTGRES_USER" "$POSTGRES_DB"
```

## Making the Tunnel Convenient

Put the forwards in `~/.ssh/config` on your machine:

```text title="~/.ssh/config"
Host honeypot
    HostName vps.example.com
    User you
    Port 2022
    LocalForward 8080 127.0.0.1:8080
    LocalForward 5000 127.0.0.1:5000
    ExitOnForwardFailure yes
```

`ExitOnForwardFailure` makes SSH refuse to connect if a local port is already
taken, instead of connecting silently without the forward. Then:

```bash
ssh -N honeypot
```

`ssh honeypot` on its own still gives you a shell with the forwards attached.

Pages refresh on a timer, so a dropped tunnel shows stale data rather than an
error:

| Page | Refresh |
|---|---|
| Overview | 120s, live feed every 20s |
| Origins | 120s |
| Payloads | 60s |
| Credentials | 30s leaderboards, 60s the rest |
| Pulse | 10s charts, 60s heatmap |
| Sessions | none |

## What Not to Do

- Do not publish 8080 or 5000 on a VPS, not even briefly to check something.
- Do not bind them to a LAN address and call it private. Docker's published
  ports bypass most host firewalls. Verify from another machine.
- If you do want a public dashboard, which is how the maintainer's instance
  runs, do not just point a reverse proxy at 8080. This compose file has no
  rate limiting, so you would be publishing an unlimited API with expensive
  aggregate queries behind it. Put a limit in the proxy first; the maintainer's
  `proxy/nginx.conf` is a worked example (30 requests per second per address
  on `/api/`, plus a short response cache).
- Do not point `VITE_API_BASE` at a separate public API host. The API sends no
  CORS headers, so the browser blocks the calls.

The forward works over port 22 or any other, so you can prove you can read the
dashboard before you hand 22 to Cowrie. That is the safer order.
