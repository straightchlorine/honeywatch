<script setup lang="ts">
  /**
   * Overview: live totals, 7-day trend, top-5 lists, choropleth map.
   * Polls every 10s (TanStack refetchInterval) for real-time tracking without SSE.
   * Map top_n=100 (all meaningful traffic); lists cap at top_n=5 to prevent sprawl.
   */
  import { computed } from 'vue'
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
  import { lazyComponent } from '@/utils/lazyComponent'

  // Lazy chunk to keep main bundle small.
  const WorldMap = lazyComponent(() => import('@/components/map/WorldMap.vue'))

  const router = useRouter()

  // Map drills to country detail page; same nav path for keyboard/SR.
  function onCountrySelect(code: string): void {
    void router.push({ name: 'countries', query: { country: code } })
  }

  // Poll every 10s: well under 60-req/min per-IP limit; decoupled from attack volume.
  const POLL_MS = 10_000
  const totalsQ = useQuery({ ...statsTotalsOptions(), refetchInterval: POLL_MS })
  const trendQ = useQuery({
    ...statsTrendOptions({ query: { period_days: 7 } }),
    refetchInterval: POLL_MS,
  })
  // Top-5 summary prevents layout sprawl; full rankings on detail pages.
  const topPasswordsQ = useQuery({
    ...statsTopPasswordsOptions({ query: { top_n: 5 } }),
    refetchInterval: POLL_MS,
  })
  const topCountriesQ = useQuery({
    ...statsTopCountriesOptions({ query: { top_n: 5 } }),
    refetchInterval: POLL_MS,
  })
  // 100 covers all meaningful traffic; separate query key avoids cache collision.
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

  // ISO id -> count map; join alpha-2 as strings; drop unmappable/null codes.
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
  Suspense rejection during setup reaches App-level boundary only.
  Error boundaries must wrap Suspense, not live inside it.
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

    <!-- No Card wrapper: map expands to full height; sphere outline frames it. -->
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
    /* Flex: 1 1 auto so map takes leftover height; page fits viewport without scroll. */
    flex: 1 1 auto;
    min-height: 0;
  }

  /* Fixed height; map (flex:1) expands to fill remaining height. */
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
    /* Expands to fill remaining height. */
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
    /* Fixed 300px height (wider map needs more room than 7-row heatmap); page scrolls. */
    .overview {
      overflow-y: auto;
    }
    .map-pane {
      flex: 0 0 auto;
      min-height: 300px;
    }
  }
</style>
