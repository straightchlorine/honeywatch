<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import {
  statsTotalsOptions,
  statsTrendOptions,
  statsTopPasswordsOptions,
  statsTopCountriesOptions,
} from '@/api/queries'
import Card from '@/components/base/Card.vue'
import Stat from '@/components/base/Stat.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorBoundary from '@/components/base/ErrorBoundary.vue'
import BarList from '@/components/base/BarList.vue'
import PageHeader from '@/components/base/PageHeader.vue'
import { fmtNumber, fmtDelta } from '@/utils/format'

const totalsQ = useQuery(statsTotalsOptions())
const trendQ = useQuery(statsTrendOptions({ query: { period_days: 7 } }))
const topPasswordsQ = useQuery(statsTopPasswordsOptions({ query: { top_n: 10 } }))
const topCountriesQ = useQuery(statsTopCountriesOptions({ query: { top_n: 10 } }))

await Promise.all([
  totalsQ.suspense(),
  trendQ.suspense(),
  topPasswordsQ.suspense(),
  topCountriesQ.suspense(),
])

const totals = computed(() => totalsQ.data.value!)
const trend = computed(() => trendQ.data.value!)
const passwordItems = computed(() => topPasswordsQ.data.value!)
const countryItems = computed(() => topCountriesQ.data.value!)

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

<template>
  <ErrorBoundary fallback-title="Could not load overview">
    <div class="overview">
      <PageHeader title="Overview" sub="Aggregated activity across all sensors." />

      <section class="stats-grid" aria-label="Key totals">
        <Card padding="md">
          <Stat :value="fmtNumber(totals.total_sessions)" label="Sessions" />
        </Card>
        <Card padding="md">
          <Stat :value="fmtNumber(totals.unique_ips)" label="Unique IPs" />
        </Card>
        <Card padding="md">
          <Stat :value="fmtNumber(totals.total_auth_attempts)" label="Auth attempts" />
        </Card>
        <Card padding="md">
          <Stat
            :value="fmtNumber(trend.current)"
            label="Trend (7d)"
            :trend="trendTone"
            :delta="trendLabel"
          />
        </Card>
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

      <section class="two-col" aria-label="Activity">
        <Card title="Activity">
          <EmptyState title="Chart coming soon" />
        </Card>
        <Card title="Heatmap">
          <EmptyState title="Chart coming soon" />
        </Card>
      </section>
    </div>
  </ErrorBoundary>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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
</style>
