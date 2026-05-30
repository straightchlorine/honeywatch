<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import {
  statsTotalsOptions,
  statsTrendOptions,
  statsTopPasswordsOptions,
  statsTopCountriesOptions,
} from '@/api/queries'
import Card from '@/components/base/Card.vue'
import Stat from '@/components/base/Stat.vue'
import BarList from '@/components/base/BarList.vue'
import PageHeader from '@/components/base/PageHeader.vue'
import { fmtNumber, fmtDelta } from '@/utils/format'
import { ALPHA2_TO_NUMERIC } from '@/components/map/alpha2-to-numeric'

// The world map lazy-loads its own chunk (d3-geo + topojson) so it stays out
// of the main bundle; it Suspends on the TopoJSON fetch independently of stats.
const WorldMap = defineAsyncComponent(() => import('@/components/map/WorldMap.vue'))

// Poll aggregates so the dashboard tracks attacks without SSE. 10s is well
// under the 60-req/min per-IP API rate limit (4 queries x 6/min = 24/min) and
// is decoupled from attack volume -- a scan storm never raises the poll rate.
const POLL_MS = 10_000
const totalsQ = useQuery({ ...statsTotalsOptions(), refetchInterval: POLL_MS })
const trendQ = useQuery({
  ...statsTrendOptions({ query: { period_days: 7 } }),
  refetchInterval: POLL_MS,
})
// Overview shows a top-5 summary; the map is the anchor and full leaderboards
// live on their own detail pages. Fewer rows also frees vertical space so the
// whole page fits the viewport.
const topPasswordsQ = useQuery({
  ...statsTopPasswordsOptions({ query: { top_n: 5 } }),
  refetchInterval: POLL_MS,
})
const topCountriesQ = useQuery({
  ...statsTopCountriesOptions({ query: { top_n: 5 } }),
  refetchInterval: POLL_MS,
})
// The map consumes the same endpoint at a higher top_n -- a separate query key,
// so no cache collision with the top-10 BarList above. Same poll cadence.
const mapCountriesQ = useQuery({
  ...statsTopCountriesOptions({ query: { top_n: 250 } }),
  refetchInterval: POLL_MS,
})

await Promise.all([
  totalsQ.suspense(),
  trendQ.suspense(),
  topPasswordsQ.suspense(),
  topCountriesQ.suspense(),
  mapCountriesQ.suspense(),
])

const totals = computed(() => totalsQ.data.value!)
const trend = computed(() => trendQ.data.value!)
const passwordItems = computed(() => topPasswordsQ.data.value!)
const countryItems = computed(() => topCountriesQ.data.value!)

// Numeric-ISO id -> count for the choropleth. Join via the committed alpha-2
// table as STRINGS; "??"/null and unmappable codes are dropped (not plotted).
const mapCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const row of mapCountriesQ.data.value ?? []) {
    if (!row.country_code) continue
    const id = ALPHA2_TO_NUMERIC[row.country_code]
    if (id) counts.set(id, row.count)
  }
  return counts
})

const trendLabel = computed(() =>
  fmtDelta({ delta: trend.value.delta, pct_change: trend.value.pct_change }),
)

const trendTone = computed<'up' | 'down' | 'neutral'>(() => {
  if (trend.value.delta > 0) return 'up'
  if (trend.value.delta < 0) return 'down'
  return 'neutral'
})

function pct(value: number, max: number): string {
  if (max <= 0) return '0%'
  return `${Math.max(2, Math.round((value / max) * 100))}%`
}

const passwordRows = computed(() => {
  let max = 0
  for (const p of passwordItems.value) if (p.count > max) max = p.count
  return passwordItems.value.map((i, idx) => ({
    key: i.password || `empty-${idx}`,
    label: i.password || '‹empty›',
    count: i.count,
    widthPct: pct(i.count, max),
    title: i.password || 'empty password',
  }))
})

const countryRows = computed(() => {
  let max = 0
  for (const c of countryItems.value) if (c.count > max) max = c.count
  return countryItems.value.map((i, idx) => {
    const label = i.country ?? i.country_code ?? 'Unknown'
    return {
      key: i.country_code ?? i.country ?? `unknown-${idx}`,
      label,
      count: i.count,
      widthPct: pct(i.count, max),
      title: label,
    }
  })
})
</script>

<!--
  No per-view ErrorBoundary here: the awaited suspense() above rejects during
  setup, before any boundary in this template could mount, so a load failure
  always propagates to the App-level ErrorBoundary (which wraps <Suspense>).
  Canonical pattern: the boundary lives OUTSIDE Suspense (see App.vue).
-->
<template>
  <div class="overview">
    <PageHeader title="Overview" />

    <section class="stats-grid" aria-label="Key totals">
      <Card padding="sm">
        <Stat :value="fmtNumber(totals.total_sessions)" label="Sessions" />
      </Card>
      <Card padding="sm">
        <Stat :value="fmtNumber(totals.unique_ips)" label="Unique IPs" />
      </Card>
      <Card padding="sm">
        <Stat :value="fmtNumber(totals.total_auth_attempts)" label="Auth attempts" />
      </Card>
      <Card padding="sm">
        <Stat
          :value="fmtNumber(trend.current)"
          label="Trend (7d)"
          :trend="trendTone"
          :delta="trendLabel"
        />
      </Card>
    </section>

    <!-- No Card: the map sits straight on the page so it can be as large as
         possible (no title row / padding) and the letterbox margins blend into
         the background. The globe keeps its own sphere outline as a frame; the
         heading stays for the document outline. -->
    <section class="map-pane" aria-label="Attack origins">
      <h2 class="map-eyebrow">Attack origins</h2>
      <Suspense>
        <WorldMap :counts="mapCounts" />
        <template #fallback>
          <div class="map-skeleton" aria-hidden="true" />
        </template>
      </Suspense>
    </section>

    <section class="two-col" aria-label="Top lists">
      <Card title="Top passwords">
        <BarList
          :items="passwordRows"
          label="Top passwords by attempt count"
          empty-text="No passwords seen yet"
        />
      </Card>

      <Card title="Top countries">
        <BarList
          :items="countryRows"
          label="Top countries by attempt count"
          empty-text="No country data yet"
        />
      </Card>
    </section>
  </div>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  /* Fill the shell's main column so the map flexes to the leftover height and
     the page fits the viewport without scrolling on desktop. */
  flex: 1 1 auto;
  min-height: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.two-col {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-3);
}

.map-pane {
  /* The hero: takes all height left between the KPI strip and the lists. */
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
}

.map-eyebrow {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1;
  margin: 0;
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
  pointer-events: none;
}

.map-skeleton {
  width: 100%;
  height: 100%;
  min-height: 240px;
  border-radius: var(--radius-md);
  background: var(--map-ocean);
}
</style>
