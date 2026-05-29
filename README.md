# Honeywatch

SSH honeypot with attack visualization and threat analysis.

|           | Health | Uptime (24h) |
|-----------|:------:|:------------:|
| Dashboard | [![](https://status.codextechnologies.org/api/v1/endpoints/external_honeywatch-dashboard/health/badge.svg)](https://status.codextechnologies.org/endpoints/external_honeywatch-dashboard) | [![](https://status.codextechnologies.org/api/v1/endpoints/external_honeywatch-dashboard/uptimes/24h/badge.svg)](https://status.codextechnologies.org/endpoints/external_honeywatch-dashboard) |
| API       | [![](https://status.codextechnologies.org/api/v1/endpoints/external_honeywatch-api/health/badge.svg)](https://status.codextechnologies.org/endpoints/external_honeywatch-api) | [![](https://status.codextechnologies.org/api/v1/endpoints/external_honeywatch-api/uptimes/24h/badge.svg)](https://status.codextechnologies.org/endpoints/external_honeywatch-api) |

## Architecture

```mermaid
graph LR
    subgraph honeypot["Honeypot VPS"]
        Cowrie[Cowrie SSH :22] -.->|HTTP only| Egress[egress-proxy]
        Cowrie -->|JSON logs| Ingestor
        Ingestor -->|INSERT as honeywatch_ingestor| PG[(Postgres)]
        API[Flask API] -->|SELECT as honeywatch_api| PG
        Grafana --> PG
        Nginx[nginx<br/>binds TS_IP only] --> API
        Nginx --> Grafana
    end

    subgraph k3s["Hetzner k3s (ArgoCD managed)"]
        Traefik[Traefik + cert-manager] --> Dashboard[Dashboard SPA]
        Traefik -->|/api/*| TSE[ts-egress sidecar]
    end

    Net((Internet)) -->|HTTPS<br/>honey.piotrkrzysztof.dev| Traefik
    TSE -.->|Tailnet| Nginx
```

The honeypot VPS runs Cowrie, ingestor, Postgres, Flask API, Grafana,
and an internal nginx that binds only to the Headscale tailnet interface.

Cowrie has no direct internet egress; outbound traffic is forced through
a tinyproxy sidecar (`egress-proxy`).

The dashboard routes `/api/*` through a Tailscale egress pod across the tailnet
to the honeypot's nginx. All k8s manifests, including the ArgoCD `Application`,
live in `k8s/`.

## What It Does

- Runs a Cowrie SSH honeypot that captures brute-force attempts
- Ingests Cowrie's JSON event log into PostgreSQL
- Serves a Vue 3 dashboard
- Exposes a public read-only REST API (Flask + flask-smorest, OpenAPI 3.1)
- Grafana wired in as a Postgres query UI for ad-hoc exploration and metrics

## Running Locally

Prerequisites: Docker, [just](https://github.com/casey/just), [uv](https://docs.astral.sh/uv/), pnpm 10.x.

```bash
cp .env.example .env
just dev          # bring up the full stack (build + detached)
just logs         # tail logs; `just logs api ingestor` to filter
just attack       # SSH into cowrie on :2222 to generate events
just down         # stop the stack
```

### Dashboard development

```bash
just dev-dashboard          # Vite dev server on http://localhost:5173
just test-dashboard-unit    # vitest run
just test-dashboard-e2e     # playwright (preview server on :4173, axe smoke)
just openapi-regen          # regenerate api/openapi.json + dashboard TS SDK
```

See `justfile` for the full command list.

## URLs

- Dashboard: http://localhost:8080
- API: http://localhost:5000 (docs at `/api/v1/swagger` and `/api/v1/redoc`)
- Grafana: http://localhost:3000

## Attributions

This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com.
