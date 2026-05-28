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

const trendLabel = computed(() => fmtDelta({ delta: trend.value.delta, pct_change: trend.value.pct_change }))

const trendTone = computed<'up' | 'down' | 'neutral'>(() => {
  if (trend.value.delta > 0) return 'up'
  if (trend.value.delta < 0) return 'down'
  return 'neutral'
})

const maxPasswordCount = computed(() => {
  let max = 0
  for (const p of passwordItems.value) if (p.count > max) max = p.count
  return max
})

const maxCountryCount = computed(() => {
  let max = 0
  for (const c of countryItems.value) if (c.count > max) max = c.count
  return max
})

function pct(value: number, max: number): string {
  if (max <= 0) return '0%'
  return `${Math.max(2, Math.round((value / max) * 100))}%`
}
</script>

<template>
  <ErrorBoundary fallback-title="Could not load overview">
    <div class="overview">
      <header class="overview-head">
        <h1 class="overview-title">Overview</h1>
        <p class="overview-sub">Aggregated activity across all sensors.</p>
      </header>

      <section class="stats-grid" aria-label="Key totals">
        <Card padding="md">
          <Stat :value="fmtNumber(totals.total_sessions)" label="Sessions" />
        </Card>
        <Card padding="md">
          <Stat :value="fmtNumber(totals.unique_ips)" label="Unique IPs" />
        </Card>
        <Card padding="md">
          <Stat
            :value="fmtNumber(totals.total_auth_attempts)"
            label="Auth attempts"
          />
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
          <EmptyState
            v-if="passwordItems.length === 0"
            title="No passwords seen yet"
            hint="Auth attempts will populate this list."
          />
          <ul v-else class="bar-list">
            <li
              v-for="(item, idx) in passwordItems"
              :key="item.password || `empty-${idx}`"
              class="bar-row"
            >
              <span
                v-if="!item.password"
                class="bar-label bar-label-empty"
                title="empty password"
                >‹empty›</span
              >
              <span v-else class="bar-label" :title="item.password">{{ item.password }}</span>
              <span class="bar-track" aria-hidden="true">
                <span class="bar-fill" :style="{ width: pct(item.count, maxPasswordCount) }" />
              </span>
              <span class="bar-count">{{ fmtNumber(item.count) }}</span>
            </li>
          </ul>
        </Card>

        <Card title="Top countries">
          <EmptyState
            v-if="countryItems.length === 0"
            title="No country data yet"
            hint="GeoIP enrichment is required for this view."
          />
          <ul v-else class="bar-list">
            <li
              v-for="item in countryItems"
              :key="item.country_code ?? item.country ?? 'unknown'"
              class="bar-row"
            >
              <span class="bar-label">
                {{ item.country ?? item.country_code ?? 'Unknown' }}
              </span>
              <span class="bar-track" aria-hidden="true">
                <span class="bar-fill" :style="{ width: pct(item.count, maxCountryCount) }" />
              </span>
              <span class="bar-count">{{ fmtNumber(item.count) }}</span>
            </li>
          </ul>
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

.overview-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.overview-title {
  margin: 0;
  font-size: var(--type-xl);
  line-height: var(--type-xl-lh);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

.overview-sub {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
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

.bar-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.bar-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(80px, 2fr) auto;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
}

.bar-label {
  color: var(--text);
  font-family: var(--font-mono);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bar-label-empty {
  color: var(--text-dim);
  font-style: italic;
}

.bar-track {
  height: 6px;
  background: var(--bg-2);
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: 999px;
  transition: width var(--motion-base) ease;
}

.bar-count {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  text-align: right;
  min-width: 3ch;
}
</style>
