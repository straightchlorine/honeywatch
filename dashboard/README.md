# Honeywatch dashboard

Vue 3 SPA for the Honeywatch honeypot. Reads from the read-only Flask API
served at `/api/v1/*` (same-origin in production, configurable in dev via
`VITE_API_BASE`).

## Stack

- Vue 3 + `<script setup>` SFCs
- TanStack Vue Query (server cache; 30s stale, no refetch-on-focus, 5xx retry ×2)
- Vite (bundler) + vue-tsc (type checking)
- Vitest + jsdom + @vue/test-utils (unit)
- Playwright + @axe-core/playwright (e2e + accessibility smoke)
- @hey-api/openapi-ts (TS client codegen from `api/openapi.json`)

## File layout

```
src/
  api/            thin wrappers + retry predicate around the generated client
    generated/    openapi-ts output (committed + drift-gated; regen via just openapi-regen)
  assets/         tokens.css and global styles
  components/
    base/         reusable primitives (Card, Stat, Spinner, LoadingState, EmptyState, BarList, PageHeader, ErrorBoundary, Pagination)
    layout/       AppShell and friends
  views/          route-level components
  router/         vue-router config
  utils/          format + attacker-text sanitize helpers
tests/
  setup.ts        jsdom polyfills (matchMedia, IntersectionObserver, ResizeObserver, EventSource)
  helpers/
    mount.ts      mountWithProviders helper (router + vue-query)
  unit/           vitest specs, mirroring src/ layout
  e2e/            playwright specs (smoke + axe)
```

## OpenAPI codegen

The backend Flask app emits an OpenAPI 3.1 spec to `api/openapi.json` (the
committed file is the source of truth). `@hey-api/openapi-ts` reads that spec
and writes a typed fetch client + tanstack-vue-query helpers into
`src/api/generated/` (committed and drift-gated, so Docker/CI builds are
hermetic and API-surface changes show up in PR diffs).

Regenerate the spec and the client together:

```bash
just openapi-regen          # flask openapi-dump + pnpm openapi:gen
```

CI fails (`just openapi-check`) if `api/openapi.json` drifts from the source.

## Tests

Unit tests (vitest, jsdom):

```bash
pnpm test                   # or: just test-dashboard-unit
pnpm test:watch
```

`tests/setup.ts` installs minimal polyfills for browser APIs that jsdom does
not implement (matchMedia, IntersectionObserver, ResizeObserver, EventSource).
`tests/helpers/mount.ts` exports `mountWithProviders`, which wires a
memory-history vue-router and a non-retrying TanStack Query client around the
component under test.

E2E (Playwright + axe):

```bash
pnpm e2e                    # or: just test-dashboard-e2e
```

`playwright.config.ts` starts `pnpm preview --port 4173 --strictPort` and
serves the built `dist/`. Make sure to `pnpm build` first.

## Token system

`src/assets/tokens.css` defines the design tokens (colors, spacing,
typography, motion) inside a `@layer tokens` block, with `@layer base` for
element resets and `@layer utilities` for helpers like `.visually-hidden`.
Components reference tokens via CSS custom properties; never hardcode colors
or sizes in component styles.
