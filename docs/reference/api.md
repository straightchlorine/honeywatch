---
description: "Every Honeywatch REST endpoint, the conventions, the privacy guarantees and the generated TypeScript client."
---

# REST API

One HTTP API, read-only. Every route is a `GET`; nothing you send it can
change what is stored. Data reaches the database only through the ingestor.

## Reaching It

Data routes live under `/api/v1`. The two health probes sit at the root.

The container listens on 5000. After the self-hosting override binds it to
`127.0.0.1`, reach it through a tunnel:

```bash
ssh -p <your-sshd-port> -N -L 5000:127.0.0.1:5000 you@your-vps
curl -s http://localhost:5000/api/v1/stats/totals
```

| Surface | Path |
| --- | --- |
| Swagger UI | `/api/v1/swagger` |
| ReDoc | `/api/v1/redoc` |
| Spec | `/api/v1/openapi.json` (OpenAPI 3.1) |
| Committed snapshot | `api/openapi.json` in the repo |

Both doc UIs load their assets from `/api/v1/static/`, so they work offline.
They do not work through the dashboard's 8080 forward, whose nginx matches
`.js` and `.css` against its own files before the `/api/` proxy. Use 5000.

!!! warning "No authentication, no rate limiting, no CORS"
    Anything that can open a TCP connection to port 5000 can read every
    aggregate you have collected and run every expensive query as often as
    it likes. Keep the port on `127.0.0.1`.

    The API also sends no `Access-Control-Allow-Origin` header, so browser
    code can only call it same-origin. The dashboard works because its nginx
    proxies `/api/` inside the compose network.

## Conventions

| Area | Rule |
| --- | --- |
| Paths | kebab-case, plural collection nouns |
| JSON fields | snake_case |
| Timestamps | ISO 8601 UTC. Newer fields end in `_at`; older ones use `timestamp`, `first_seen`, `last_seen` |
| Pagination | `page` and `per_page` (max 100); body is `{items, meta}` with `meta` as `{page, per_page, pages, total}` |
| Errors | `{code, status, message}`, plus `errors` naming the fields. 422 for validation, 404 for not found, 503 for unhealthy |

JSON responses carry `Cache-Control: public, max-age=30`, except the map (120)
and a country detail (300). Errors and the spec are `no-store`.

## Endpoints

### Sessions

| Path | Returns |
| --- | --- |
| `/api/v1/sessions/` | Paginated session summaries, plus `max_interest` for normalizing scores |
| `/api/v1/sessions/{session_id}` | Full detail: auth attempts, commands, downloads, client info. 404 if unknown |

The trailing slash on the list route is part of the path. Session ids are
Cowrie's opaque identifiers; get them from the list rather than guessing.

Query parameters for the list:

| Parameter | Default | Notes |
| --- | --- | --- |
| `page` | 1 | 1 to 50000 |
| `per_page` | 20 | 1 to 100 |
| `q` | | Lowercase hex prefix of a session id, 2 to 64 characters |
| `country` | | Two-letter code |
| `category` | | `active`, `login`, `failed` or `probe` |
| `sort` | `recent` | `recent`, `country`, `active`, `interest` or `duration` |
| `has` | | Comma-separated flags, e.g. `commands,success` |
| `sha256` | | Sessions that downloaded that payload |

### Stats

| Path | Returns |
| --- | --- |
| `/api/v1/stats/totals` | Sessions, auth attempts, unique sources |
| `/api/v1/stats/trend` | Session count over `period_days` against the preceding window |
| `/api/v1/stats/activity` | Session counts by hour, day or month |
| `/api/v1/stats/heatmap` | Session counts per weekday and hour |
| `/api/v1/stats/outcomes` | Session counts per outcome bucket |
| `/api/v1/stats/auth-outcomes` | Accept/reject split across all auth attempts |
| `/api/v1/stats/top-passwords` | Top-N passwords by count |
| `/api/v1/stats/top-credentials` | Top-N credentials by the chosen metric |
| `/api/v1/stats/password-composition` | Length histogram plus character-class breakdown |
| `/api/v1/stats/passwords-by-length` | Top-N passwords of one length |
| `/api/v1/stats/top-countries` | Top-N countries by session count |
| `/api/v1/stats/countries` | Per-country leaderboard by the chosen sort |
| `/api/v1/stats/countries/{a2}` | One country: totals, networks, credentials, trend. 404 if unknown |
| `/api/v1/stats/map` | Choropleth values plus city markers for the Overview map |
| `/api/v1/stats/asns` | Top-N source networks |
| `/api/v1/stats/ssh-clients` | Top-N client version banners |
| `/api/v1/stats/fingerprints` | Top-N offered public key fingerprints by distinct source count |
| `/api/v1/stats/downloads` | Top-N payloads by SHA-256 |
| `/api/v1/stats/downloads/{sha256}` | One payload plus its per-country breakdown. 404 if unknown |
| `/api/v1/stats/tcpip-destinations` | Top-N port-forward destinations by network and port |

`top_n` is 1 to 100 and defaults to 10, except on `countries` where it
defaults to 50. `country` is accepted by `activity`, `asns`, `heatmap`,
`outcomes`, `trend` and `top-credentials`; `asns` and `top-credentials` also
take `??` for traffic that could not be geolocated.

Endpoint-specific: `bucket` on `activity`; `sort` on `countries`;
`period_days` (1 to 365) on `trend`; `length` (0 to 16, required) on
`passwords-by-length`; `by`, `metric` and `outcome` on `top-credentials`. The
spec has the enums.

### Health

| Path | Returns |
| --- | --- |
| `/health` | Static `{"status": "ok"}`. Never touches the database |
| `/health/ready` | `{"status": "ready"}`, or 503 `{"status": "unavailable", "reason": "db"}` |

The Docker healthcheck uses `/health`, so a container with a dead database
stays healthy and is not restarted. Use `/health/ready` to find out whether
data is being served. Neither is under `/api/`, so the dashboard's proxy does
not cover them.

## Privacy

No response contains a source IP address. Addresses are stored only to join a
session to its geolocation row, and no serializer emits one.

Attacker-controlled text is a separate problem: anyone can type an address
into a command or a password. Every such field passes through a redaction
step that replaces IPv4 and IPv6 literals with `<ip>` before serialization.
That covers commands, download URLs, usernames, passwords and client banners.
Where a schema promises a field is never an address, the value becomes `null`
instead.

Redaction over-reaches on purpose: a bare 10-digit integer in a command, such
as a Unix timestamp, is blotted too. The `<ip>` token is a literal string the
dashboard depends on.

It is applied by each serializer, not by a response-wide filter. A new route
that returns attacker text must redact it itself.

## Generated Clients

The dashboard's TypeScript SDK is generated from `api/openapi.json` by
`@hey-api/openapi-ts` into `dashboard/src/api/generated` and committed.
Regenerate both with:

```bash
just openapi-regen
```

CI fails when the spec or SDK drift from the code. See
[Development](development.md) for the gate and its one surprise.

The spec is plain OpenAPI 3.1, so any generator can consume `api/openapi.json`
or fetch it live from `/api/v1/openapi.json`.
