<script setup lang="ts">
  import { computed, defineAsyncComponent } from 'vue'
  import { useRouter } from 'vue-router'
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
  import { countryDisplayName } from '@/utils/countries'
  import { ALPHA2_TO_NUMERIC } from '@/components/map/alpha2-to-numeric'

  // The world map lazy-loads its own chunk (d3-geo + topojson) so it stays out
  // of the main bundle; it Suspends on the TopoJSON fetch independently of stats.
  const WorldMap = defineAsyncComponent(() => import('@/components/map/WorldMap.vue'))

  const router = useRouter()

  // Clicking a country on the map drills into its full breakdown on the
  // Countries page (the map's own offscreen list drives the same nav for
  // keyboard/SR users).
  function onCountrySelect(code: string): void {
    void router.push({ name: 'countries', query: { country: code } })
  }

  // Poll aggregates so the dashboard tracks attacks without SSE. 10s is well
  // under the 60-req/min per-IP API rate limit (4 queries x 6/min = 24/min) and
  // is decoupled from attack volume -- a scan storm never raises the poll rate.
  const POLL_MS = 10_000
  const totalsQ = useQuery({ ...statsTotalsOptions(), refetchInterval: POLL_MS })
  const trendQ = useQuery({
    ...statsTrendOptions({ query: { period_days: 7 } }),
    refetchInterval: POLL_MS,
  })
  // Overview shows a top-5 summary; the map is the anchor and the full
  // leaderboards live on their own detail pages (Countries / Credentials).
  // Capped low so the lists can never grow tall enough to squeeze the map, on
  // top of the flex:0 0 auto pin below.
  const topPasswordsQ = useQuery({
    ...statsTopPasswordsOptions({ query: { top_n: 5 } }),
    refetchInterval: POLL_MS,
  })
  const topCountriesQ = useQuery({
    ...statsTopCountriesOptions({ query: { top_n: 5 } }),
    refetchInterval: POLL_MS,
  })
  // The map consumes the same endpoint at the API's max top_n (100) - a separate
  // query key, so no cache collision with the top-10 BarList above. 100 covers
  // every country with meaningful traffic; the long tail beyond rank 100 (1-2
  // hits each) would be the faintest amber anyway. Same poll cadence.
  const mapCountriesQ = useQuery({
    ...statsTopCountriesOptions({ query: { top_n: 100 } }),
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
      const label = countryDisplayName(i.country_code, i.country)
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
        <WorldMap :counts="mapCounts" @select="onCountrySelect" />
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

  /* KPI strip + lists are fixed-height (flex:0 0 auto) so they neither grow nor
   shrink - the map (.map-pane, the only flex:1 item) always takes exactly the
   leftover height. */
  .stats-grid {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-3);
  }

  .two-col {
    flex: 0 0 auto;
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

  @media (max-width: 768px) {
    /* Below md the KPI strip + two lists would squeeze the flexing map below its
     legible floor, so the SVG + legend overflowed downward onto the lists. Same
     play as ActivityView: stop hard-fitting -- pin the hero to a fixed height and
     let the page scroll. 300px (vs the heatmap's 240) because the wide world map
     needs more vertical room than the 7-row heatmap to stay readable. */
    .overview {
      overflow-y: auto;
    }
    .map-pane {
      flex: 0 0 auto;
      min-height: 300px;
    }
  }
</style>
