<script setup lang="ts">
  /** Honeycomb heatmap (hour x weekday), daily session columns, KPI grid, and readings from activity data. */
  import { computed } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useQuery, keepPreviousData } from '@tanstack/vue-query'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import {
    statsHeatmapOptions,
    statsActivityOptions,
    statsTrendOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import StatTile from '@/components/base/StatTile.vue'
  import ChipSelect from '@/components/base/ChipSelect.vue'
  import InsightNote from '@/components/base/InsightNote.vue'
  import InfoDot from '@/components/base/InfoDot.vue'
  import HexHeatmap from '@/components/charts/HexHeatmap.vue'
  import DailyColumns from '@/components/charts/DailyColumns.vue'
  import { buildHeatmapGrid } from '@/utils/heatmapGrid'
  import { busiestHour, busiestWeekday, peakDay } from '@/utils/activityKpis'
  import { pulseReadings } from '@/utils/pulseReadings'
  import { fmtNumber, fmtDelta } from '@/utils/format'
  import { useCountryFilter } from '@/composables/useCountryFilter'
  import { useCountryOptions } from '@/composables/useCountryOptions'

  // The all-time hour x weekday heatmap barely moves minute to minute, so it
  // polls far less often than the daily/trend queries.
  const POLL_MS = 10_000
  const POLL_SLOW_MS = 60_000

  const route = useRoute()
  const router = useRouter()

  // Country scope lives in the URL (?country=XX); empty = all countries.
  const { country, countryQuery } = useCountryFilter()
  const countryOptions = useCountryOptions('The world')
  const tt = useHwTooltip()

  // keepPreviousData holds the prior country's data on screen while the new
  // scope loads, so switching country never leaves the charts momentarily
  // empty.
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

  const heatmapPoints = computed(() => heatmapQ.data.value ?? [])
  const days = computed(() => dayQ.data.value ?? [])
  const trend = computed(() => trendQ.data.value)

  // KPIs and readings derive from heatmapPoints/days alone, so they cannot
  // contradict each other. The trend tile is the one exception (trendQ).
  const heatmapGrid = computed(() => buildHeatmapGrid(heatmapPoints.value))
  const bHour = computed(() => busiestHour(heatmapPoints.value))
  const bDay = computed(() => busiestWeekday(heatmapPoints.value))
  const pDay = computed(() => peakDay(days.value))
  const readings = computed(() => pulseReadings(heatmapGrid.value))

  const trendTone = computed<'up' | 'down' | 'neutral'>(() => {
    if (!trend.value) return 'neutral'
    if (trend.value.delta > 0) return 'up'
    if (trend.value.delta < 0) return 'down'
    return 'neutral'
  })
  const trendLabel = computed(() =>
    trend.value ? fmtDelta({ delta: trend.value.delta, pct_change: trend.value.pct_change }) : '',
  )

  // Sparkline needs >= 2 points to draw a line.
  const spark = computed(() => {
    const vals = days.value.slice(-7).map((b) => b.count)
    return vals.length > 1 ? vals : [0, 0]
  })

  const totalHeatmapSessions = computed(() =>
    heatmapPoints.value.reduce((sum, p) => sum + p.count, 0),
  )
  const total30dSessions = computed(() =>
    days.value.reduce((sum, b) => sum + b.count, 0),
  )


  function setCountry(value: string): void {
    const query = { ...route.query }
    if (value) query.country = value
    else delete query.country
    void router.push({ query })
  }

  function sessionsDelta(count: number): string | undefined {
    return count > 0 ? `${fmtNumber(count)} sessions` : undefined
  }

  /** Skip tooltip repositioning when clientX/clientY are undefined (focus events carry no coordinates). */
  function moveIfPositioned(e: { clientX?: number; clientY?: number }): void {
    if (e.clientX !== undefined && e.clientY !== undefined) {
      tt.move({ clientX: e.clientX, clientY: e.clientY })
    }
  }

  function showTrendTooltip(e: { clientX?: number; clientY?: number }): void {
    tt.show('7-day trend', [
      ['This week', fmtNumber(trend.value?.current ?? 0)],
      ['Prior week', fmtNumber(trend.value?.previous ?? 0)],
      [
        'Change',
        trend.value
          ? fmtDelta({ delta: trend.value.delta, pct_change: trend.value.pct_change })
          : 'n/a',
        trend.value && trend.value.delta > 0
          ? 'pos'
          : trend.value && trend.value.delta < 0
            ? 'neg'
            : undefined,
      ],
    ])
    moveIfPositioned(e)
  }

  function showBusiestHourTooltip(e: { clientX?: number; clientY?: number }): void {
    const total = totalHeatmapSessions.value
    const rows: Array<[string, string]> =
      total > 0
        ? [['Share', `${((bHour.value.count / total) * 100).toFixed(1)}% of all sessions`]]
        : []
    tt.show('Busiest hour', rows)
    moveIfPositioned(e)
  }

  function showBusiestDayTooltip(e: { clientX?: number; clientY?: number }): void {
    const total = totalHeatmapSessions.value
    const rows: Array<[string, string]> = []
    if (total > 0) {
      rows.push(['Share', `${((bDay.value.count / total) * 100).toFixed(1)}% of all sessions`])
    }
    rows.push(['Single-day peak', `${pDay.value.value} (${fmtNumber(pDay.value.count)}, last 30 days)`])
    tt.show('Busiest day', rows)
    moveIfPositioned(e)
  }

  function showPeakDayTooltip(e: { clientX?: number; clientY?: number }): void {
    const total = total30dSessions.value
    const rows: Array<[string, string]> = [['Window', 'last 30 days']]
    if (total > 0) {
      rows.push(['Share', `${((pDay.value.count / total) * 100).toFixed(1)}% of the 30-day total`])
    }
    tt.show('Peak day', rows)
    moveIfPositioned(e)
  }
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar current="pulse" />
    </template>

    <div class="pulse">
      <div class="page-head">
        <h1 class="pulse-title">Pulse</h1>
        <span class="sub">when attacks happen &middot; all times UTC</span>
        <span class="spacer" />
        <span class="country-select">
          <ChipSelect
            label="Country filter"
            :options="countryOptions"
            :model-value="country"
            @update:model-value="setCountry"
          />
        </span>
      </div>


      <div class="grid-main">
        <HwCard
          title="Session rhythm &middot; hour &times; weekday"
          note="grouped by hour of day, UTC"
          class="comb-card"
        >
          <HexHeatmap class="comb-chart" :points="heatmapPoints" />
        </HwCard>

        <div class="bottom-row">
          <div class="kpi-grid">
            <StatTile
              label="7-day trend"
              :value="fmtNumber(trend?.current ?? 0)"
              :spark="spark"
            >
              <template #label-extra>
                <InfoDot title="7-day trend" text="Sessions in the last 7 days compared with the 7 days before." />
              </template>
              <template #meta>
                <span
                  class="trend-delta"
                  :class="`trend-${trendTone}`"
                  role="button"
                  tabindex="0"
                  @pointerenter="showTrendTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showTrendTooltip({})"
                  @blur="tt.hide()"
                >
                  {{ trendLabel }}
                </span>
              </template>
            </StatTile>
            <StatTile label="Busiest hour" :value="bHour.value">
              <template #label-extra>
                <InfoDot title="Busiest hour" text="The hour of day (UTC) with the most sessions, over all time." />
              </template>
              <template v-if="sessionsDelta(bHour.count)" #meta>
                <button
                  type="button"
                  class="kpi-meta-button"
                  aria-label="Busiest hour: share of all sessions"
                  @pointerenter="showBusiestHourTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showBusiestHourTooltip({})"
                  @blur="tt.hide()"
                >
                  {{ sessionsDelta(bHour.count) }}
                </button>
              </template>
            </StatTile>
            <StatTile label="Busiest day" :value="bDay.value">
              <template #label-extra>
                <InfoDot title="Busiest day" text="The weekday with the most sessions on average, over all time." />
              </template>
              <template v-if="sessionsDelta(bDay.count)" #meta>
                <button
                  type="button"
                  class="kpi-meta-button"
                  aria-label="Busiest day: share of all sessions and single-day peak"
                  @pointerenter="showBusiestDayTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showBusiestDayTooltip({})"
                  @blur="tt.hide()"
                >
                  {{ sessionsDelta(bDay.count) }}
                </button>
              </template>
            </StatTile>
            <StatTile label="Peak day" :value="pDay.value">
              <template #label-extra>
                <InfoDot title="Peak day" text="The date with the most sessions in the last 30 days." />
              </template>
              <template v-if="sessionsDelta(pDay.count)" #meta>
                <button
                  type="button"
                  class="kpi-meta-button"
                  aria-label="Peak day: 30-day window and share"
                  @pointerenter="showPeakDayTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showPeakDayTooltip({})"
                  @blur="tt.hide()"
                >
                  {{ sessionsDelta(pDay.count) }}
                </button>
              </template>
            </StatTile>
          </div>

          <HwCard
            title="Daily sessions"
            note="last 30 days &middot; peak labeled"
            class="daily-card"
          >
            <DailyColumns :buckets="days" />
          </HwCard>

          <HwCard title="Readings" class="readings-card">
            <div class="readings-notes">
              <InsightNote v-for="r in readings" :key="r">{{ r }}</InsightNote>
              <p v-if="!readings.length" class="readings-empty">
                Not enough data yet for readings.
              </p>
            </div>
          </HwCard>
        </div>
      </div>
    </div>
  </PageShell>
</template>

<style scoped>
  .pulse {
    display: flex;
    flex-direction: column;
    gap: 14px;
    flex: 1 1 auto;
    min-height: 0;
  }

  .page-head {
    flex: 0 0 auto;
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
  }

  .pulse-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text);
  }

  .sub {
    font-size: 12.5px;
    color: var(--text-dim);
  }

  .spacer {
    flex: 1;
  }

  .country-select {
    min-width: 148px;
  }


  .grid-main {
    /* Reserve space for chrome (~134px) and bottom row (262px: 3 readings at 2 lines
       = 206px + 24px heading + 32px padding) to prevent content overflow at viewports
       <1080px tall. Trade-off: costs comb ~11% width at 900px viewport. */
    --comb-reserved: 434px;
    --comb-chrome: 106px;
    flex: 1 1 auto;
    min-height: 0;
    display: grid;
    /* 250px minimum for 3 two-line readings; below this the comb shrinks instead. */
    grid-template-rows: auto minmax(250px, 1fr);
    gap: 14px;
  }

  /* Cap width instead of height to preserve aspect ratio and prevent bottom-row overflow at min desktop height (~768px). */
  .comb-card {
    min-height: 0;
    max-height: calc(100dvh - var(--comb-reserved));
  }

  .comb-chart :deep(.hex-chart) {
    /* width:100% is load-bearing: `margin-inline: auto` on a flex item turns
       off cross-axis stretch, so without an explicit width the box collapses
       to the svg's 300px default intrinsic size instead of filling the card. */
    width: 100%;
    max-width: calc((100dvh - var(--comb-reserved) - var(--comb-chrome)) * 3.911);
    margin-inline: auto;
  }

  .comb-chart {
    flex: 1;
    min-height: 0;
  }

  /* KPI tiles: 360px min (labels wrap at 320px). Readings: 380px min (clips at 300px on short viewports). */
  .bottom-row {
    display: grid;
    grid-template-columns: 360px 1fr 380px;
    gap: 14px;
    min-height: 0;
  }

  .kpi-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    gap: 10px;
    min-height: 0;
  }

  .kpi-grid :deep(.stat-tile) {
    min-height: 88px;
    /* safe center prevents clipping overfull content at the top. */
    justify-content: safe center;
    align-items: safe center;
    text-align: center;
  }

  .trend-up {
    color: var(--ok);
  }
  .trend-down {
    color: var(--bad);
  }
  .trend-neutral {
    color: var(--text-muted);
  }

  /* .trend-delta must not have button reset or color:inherit will silently override .trend-up/.trend-down. */
  .kpi-meta-button {
    appearance: none;
    background: transparent;
    border: none;
    padding: 0;
    color: inherit;
    font: inherit;
  }
  .trend-delta,
  .kpi-meta-button {
    cursor: pointer;
    transition: opacity var(--motion-fast);
  }
  .trend-delta:hover,
  .kpi-meta-button:hover {
    opacity: 0.8;
  }
  .trend-delta:focus-visible,
  .kpi-meta-button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-radius: 2px;
  }

  .daily-card,
  .readings-card {
    min-height: 0;
  }

  /* Three readings max; safe center prevents overflow clipping the first. */
  .readings-notes {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    justify-content: safe center;
  }

  .readings-notes :deep(.insight) {
    padding: 8px 12px;
    line-height: 1.45;
    align-items: center;
    text-align: center;
  }

  /* Lets the text centre in the leftover width while the bullet stays pinned left. */
  .readings-notes :deep(.insight) > span {
    flex: 1;
  }

  .readings-empty {
    margin: 0;
    font-size: 13px;
    color: var(--text-dim);
  }

  @media (max-width: 900px) {
    .grid-main {
      display: flex;
      flex-direction: column;
    }

    .comb-card {
      max-height: none;
      overflow: visible;
    }

    .bottom-row {
      display: flex;
      flex-direction: column;
    }

    .kpi-grid {
      grid-template-columns: 1fr 1fr;
      grid-template-rows: auto auto;
    }

    .daily-card {
      min-height: 200px;
    }
  }
</style>
