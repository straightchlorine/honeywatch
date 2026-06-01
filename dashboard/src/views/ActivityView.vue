<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, keepPreviousData } from '@tanstack/vue-query'
import {
  statsHeatmapOptions,
  statsActivityOptions,
  statsTrendOptions,
  statsTopCountriesOptions,
} from '@/api/queries'
import Card from '@/components/base/Card.vue'
import Stat from '@/components/base/Stat.vue'
import Dropdown from '@/components/base/Dropdown.vue'
import ActivityHeatmap from '@/components/charts/ActivityHeatmap.vue'
import ActivityTimeline from '@/components/charts/ActivityTimeline.vue'
import { fmtNumber, fmtDelta } from '@/utils/format'
import { busiestHour, busiestWeekday, peakDay } from '@/utils/activityKpis'

type Opt = { value: string; label: string }

// The daily activity + 7-day trend visibly move minute to minute; the all-time
// weekday x hour heatmap barely changes, so it polls far less often (and skips
// re-running the heaviest all-time aggregate on the fast loop).
const POLL_MS = 10_000
const POLL_SLOW_MS = 60_000

const route = useRoute()
const router = useRouter()

// Country scope lives in the URL (?country=XX); empty = all countries.
const country = computed(() => {
  const c = route.query.country
  return typeof c === 'string' && /^[A-Za-z]{2}$/.test(c) ? c.toUpperCase() : ''
})
const countryQuery = computed(() => (country.value ? { country: country.value } : {}))

// keepPreviousData keeps the prior country's data on screen while the new query
// loads, so changing the scope never leaves data.value momentarily undefined
// (which would crash the unguarded trend read). Mirrors SessionsView.
const heatmapQ = useQuery(
  computed(() => ({
    ...statsHeatmapOptions({ query: countryQuery.value }),
    refetchInterval: POLL_SLOW_MS,
    staleTime: POLL_SLOW_MS,
    placeholderData: keepPreviousData,
  })),
)
const dayQ = useQuery(
  computed(() => ({
    ...statsActivityOptions({ query: { bucket: 'day', ...countryQuery.value } }),
    refetchInterval: POLL_MS,
    placeholderData: keepPreviousData,
  })),
)
const trendQ = useQuery(
  computed(() => ({
    ...statsTrendOptions({ query: { period_days: 7, ...countryQuery.value } }),
    refetchInterval: POLL_MS,
    placeholderData: keepPreviousData,
  })),
)

await Promise.all([heatmapQ.suspense(), dayQ.suspense(), trendQ.suspense()])

const heatmap = computed(() => heatmapQ.data.value ?? [])
const days = computed(() => dayQ.data.value ?? [])
const trend = computed(() => trendQ.data.value!)

const bHour = computed(() => busiestHour(heatmap.value))
const bDay = computed(() => busiestWeekday(heatmap.value))
const pDay = computed(() => peakDay(days.value))

const trendTone = computed<'up' | 'down' | 'neutral'>(() => {
  if (trend.value.delta > 0) return 'up'
  if (trend.value.delta < 0) return 'down'
  return 'neutral'
})
const trendLabel = computed(() =>
  fmtDelta({ delta: trend.value.delta, pct_change: trend.value.pct_change }),
)

// Country dropdown options reuse the top-countries leaderboard (max 100). The
// default ("") scopes to every country and reads as "World" in the title.
const countriesQ = useQuery({ ...statsTopCountriesOptions({ query: { top_n: 100 } }) })
const countryOptions = computed<Opt[]>(() => [
  { value: '', label: 'the world' },
  ...(countriesQ.data.value ?? [])
    .filter((c) => c.country_code && /^[A-Za-z]{2}$/.test(c.country_code))
    .map((c) => ({
      value: c.country_code as string,
      label: (c.country ?? c.country_code) as string,
    })),
])

// After the first successful load, keepPreviousData holds the last good data on
// screen even if a background poll fails; surface that so the numbers are not
// silently stale (the queries keep retrying on their interval).
const isStale = computed(() => heatmapQ.isError.value || dayQ.isError.value || trendQ.isError.value)

function setCountry(value: string): void {
  void router.push({ query: value ? { country: value } : {} })
}

function sessionsDelta(count: number): string | undefined {
  return count > 0 ? `${fmtNumber(count)} sessions` : undefined
}
</script>

<template>
  <div class="activity">
    <div class="head-row">
      <h1 class="activity-title">Activity of</h1>
      <span id="a-scope-label" class="visually-hidden">Country scope</span>
      <Dropdown
        button-id="a-scope"
        label-id="a-scope-label"
        class="scope-dd"
        :model-value="country"
        :options="countryOptions"
        @update:model-value="setCountry"
      />
      <span v-if="isStale" class="stale" role="status">⚠ data may be stale — retrying</span>
    </div>

    <section class="stats-grid" aria-label="Temporal metrics">
      <Card padding="sm">
        <Stat
          :value="bHour.value"
          label="Busiest hour · UTC"
          trend="neutral"
          :delta="sessionsDelta(bHour.count)"
        />
      </Card>
      <Card padding="sm">
        <Stat
          :value="bDay.value"
          label="Busiest day"
          trend="neutral"
          :delta="sessionsDelta(bDay.count)"
        />
      </Card>
      <Card padding="sm">
        <Stat
          :value="pDay.value"
          label="Peak day"
          trend="neutral"
          :delta="sessionsDelta(pDay.count)"
        />
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

    <Card title="Sessions by hour &amp; weekday" fill padding="sm" class="heatmap-pane">
      <ActivityHeatmap :points="heatmap" />
    </Card>

    <Card title="Daily activity" class="timeline-pane">
      <ActivityTimeline :buckets="days" label="Daily session counts" />
    </Card>
  </div>
</template>

<style scoped>
.activity {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  flex: 1 1 auto;
  min-height: 0;
}

.head-row {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.activity-title {
  margin: 0;
  font-size: var(--type-xl);
  line-height: var(--type-xl-lh);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

/* Bump the inline scope picker so it reads as part of the heading phrase.
   min-width:0 lets it shrink instead of wrapping the sentence on narrow widths. */
.scope-dd :deep(.dd-button) {
  font-size: var(--type-base);
  font-weight: 600;
  color: var(--accent);
  min-width: 0;
}

.stale {
  font-size: var(--type-xs);
  color: var(--warning);
  white-space: nowrap;
}

.stats-grid {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.heatmap-pane {
  flex: 1 1 auto;
  min-height: 0;
}

.timeline-pane {
  flex: 0 0 auto;
}

@media (max-width: 768px) {
  /* The KPI grid + fixed timeline would squeeze the heatmap below its legible
     row floor, so below md the page scrolls instead of hard-fitting. */
  .activity {
    overflow-y: auto;
    min-height: 0;
  }
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .heatmap-pane {
    /* Keep the heatmap tall enough for 7 legible rows once the page scrolls. */
    flex: 0 0 auto;
    min-height: 240px;
  }
}
</style>
