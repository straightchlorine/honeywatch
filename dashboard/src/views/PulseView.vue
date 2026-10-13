<script setup lang="ts">
  /** Honeycomb heatmap (hour x weekday), daily session columns, KPI grid, and readings from activity data. */
  import { computed } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useQuery, keepPreviousData } from '@tanstack/vue-query'
  import { useHwTooltip, type TooltipRow } from '@/composables/useHwTooltip'
  import {
    statsHeatmapOptions,
    statsActivityOptions,
    statsTrendOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import { suspenseAll } from '@/api/queries'
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
  import { pulseReadings, quietReading } from '@/utils/pulseReadings'
  import { fmtNumber, fmtDelta, fmtDeltaParts } from '@/utils/format'
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

  await suspenseAll(heatmapQ, dayQ, trendQ)

  const heatmapPoints = computed(() => heatmapQ.data.value ?? [])
  const days = computed(() => dayQ.data.value ?? [])
  const trend = computed(() => trendQ.data.value)

  // KPIs and readings derive from heatmapPoints/days alone, so they cannot
  // contradict each other. The trend tile is the one exception (trendQ).
  const heatmapGrid = computed(() => buildHeatmapGrid(heatmapPoints.value))
  const bHour = computed(() => busiestHour(heatmapPoints.value))
  const bDay = computed(() => busiestWeekday(heatmapPoints.value))
  const pDay = computed(() => peakDay(days.value))
  const readings = computed(() => {
    const base = pulseReadings(heatmapGrid.value)
    const quiet = base.length ? quietReading(heatmapGrid.value) : null
    return quiet ? [...base, quiet] : base
  })

  const trendTone = computed<'up' | 'down' | 'neutral'>(() => {
    if (!trend.value) return 'neutral'
    if (trend.value.delta > 0) return 'up'
    if (trend.value.delta < 0) return 'down'
    return 'neutral'
  })
  const trendParts = computed(() =>
    trend.value
      ? fmtDeltaParts({ delta: trend.value.delta, pct_change: trend.value.pct_change })
      : { abs: '', pct: null },
  )

  const totalHeatmapSessions = computed(() =>
    heatmapPoints.value.reduce((sum, p) => sum + p.count, 0),
  )
  const total30dSessions = computed(() => days.value.reduce((sum, b) => sum + b.count, 0))

  function setCountry(value: string): void {
    const query = { ...route.query }
    if (value) query.country = value
    else delete query.country
    void router.push({ query })
  }

  function sessionsDelta(count: number): string | undefined {
    return count > 0 ? `${fmtNumber(count)} sessions` : undefined
  }

  /** Share of a total as a one-decimal percentage, e.g. "12.5%". */
  function sharePct(count: number, total: number): string {
    return `${((count / total) * 100).toFixed(1)}%`
  }

  // Accessible names repeat the visible figure and the tooltip facts: the tooltip
  // is not linked to its button, so assistive tech would never reach those facts.
  // Each button renders only when its count is above zero, so the totals are above zero too.
  function trendAriaLabel(): string {
    const { abs, pct } = trendParts.value
    const shown = pct ? `${abs} \u00b7 ${pct}` : abs
    return `7-day trend: ${shown} vs prior week`
  }

  function busiestHourAriaLabel(): string {
    const { value, count } = bHour.value
    const share = sharePct(count, totalHeatmapSessions.value)
    return `Busiest hour ${value}: ${fmtNumber(count)} sessions, ${share} of all sessions`
  }

  function topWeekdayAriaLabel(): string {
    const { value, count } = bDay.value
    const share = sharePct(count, totalHeatmapSessions.value)
    const peak = pDay.value
    return (
      `Top weekday ${value}: ${fmtNumber(count)} sessions, ${share} of all sessions. ` +
      `Single-day peak ${peak.value}, ${fmtNumber(peak.count)} sessions in the last 30 days.`
    )
  }

  function peakDateAriaLabel(): string {
    const { value, count } = pDay.value
    const share = sharePct(count, total30dSessions.value)
    return `Peak date ${value}: ${fmtNumber(count)} sessions, ${share} of the 30-day total`
  }

  type TipEvent = { clientX?: number; clientY?: number; currentTarget?: EventTarget | null }

  // Focus carries no pointer coordinates: anchor the bubble to the button instead.
  function presentTip(e: TipEvent, title: string, rows: TooltipRow[]): void {
    if (e.clientX === undefined && e.currentTarget instanceof Element) {
      tt.showAt(e.currentTarget, title, rows)
    } else tt.show(title, rows, undefined, e)
  }

  function showTrendTooltip(e: TipEvent): void {
    presentTip(
      e,
      '7-day trend',
      [
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
      ],
    )
  }

  function showBusiestHourTooltip(e: TipEvent): void {
    const total = totalHeatmapSessions.value
    const rows: Array<[string, string]> =
      total > 0 ? [['Share', `${sharePct(bHour.value.count, total)} of all sessions`]] : []
    presentTip(e, 'Busiest hour', rows)
  }

  function showBusiestDayTooltip(e: TipEvent): void {
    const total = totalHeatmapSessions.value
    const rows: Array<[string, string]> = []
    if (total > 0) {
      rows.push(['Share', `${sharePct(bDay.value.count, total)} of all sessions`])
    }
    rows.push([
      'Single-day peak',
      `${pDay.value.value} (${fmtNumber(pDay.value.count)}, last 30 days)`,
    ])
    presentTip(e, 'Top weekday', rows)
  }

  function showPeakDayTooltip(e: TipEvent): void {
    const total = total30dSessions.value
    const rows: Array<[string, string]> = [['Window', 'last 30 days']]
    if (total > 0) {
      rows.push(['Share', `${sharePct(pDay.value.count, total)} of the 30-day total`])
    }
    presentTip(e, 'Peak date', rows)
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
          title="Session rhythm"
          note="hour &times; weekday, UTC"
          class="comb-card"
        >
          <HexHeatmap class="comb-chart" :points="heatmapPoints" />
        </HwCard>

        <div class="bottom-row">
          <div class="kpi-grid">
            <StatTile label="7-day trend" :value="fmtNumber(trend?.current ?? 0)">
              <template #label-extra>
                <InfoDot
                  title="7-day trend"
                  text="Sessions in the last 7 days compared with the 7 days before: the change in sessions, then as a percentage."
                />
              </template>
              <template #meta>
                <button
                  type="button"
                  class="kpi-meta-button"
                  :class="`trend-${trendTone}`"
                  :aria-label="trendAriaLabel()"
                  @pointerenter="showTrendTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showTrendTooltip($event)"
                  @blur="tt.hide()"
                >
                  {{ trendParts.abs }}
                  <span v-if="trendParts.pct">&middot; </span>
                  <span class="trend-pct">{{ trendParts.pct }}</span>
                </button>
              </template>
            </StatTile>
            <StatTile label="Busiest hour" :value="bHour.value">
              <template #label-extra>
                <InfoDot
                  title="Busiest hour"
                  text="The hour of day (UTC) with the most sessions, over all time."
                />
              </template>
              <template v-if="sessionsDelta(bHour.count)" #meta>
                <button
                  type="button"
                  class="kpi-meta-button"
                  :aria-label="busiestHourAriaLabel()"
                  @pointerenter="showBusiestHourTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showBusiestHourTooltip($event)"
                  @blur="tt.hide()"
                >
                  {{ sessionsDelta(bHour.count) }}
                </button>
              </template>
            </StatTile>
            <StatTile label="Top weekday" :value="bDay.value">
              <template #label-extra>
                <InfoDot
                  title="Top weekday"
                  text="The weekday with the most sessions on average, over all time."
                />
              </template>
              <template v-if="sessionsDelta(bDay.count)" #meta>
                <button
                  type="button"
                  class="kpi-meta-button"
                  :aria-label="topWeekdayAriaLabel()"
                  @pointerenter="showBusiestDayTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showBusiestDayTooltip($event)"
                  @blur="tt.hide()"
                >
                  {{ sessionsDelta(bDay.count) }}
                </button>
              </template>
            </StatTile>
            <StatTile label="Peak date" :value="pDay.value">
              <template #label-extra>
                <InfoDot
                  title="Peak date"
                  text="The date with the most sessions in the last 30 days."
                />
              </template>
              <template v-if="sessionsDelta(pDay.count)" #meta>
                <button
                  type="button"
                  class="kpi-meta-button"
                  :aria-label="peakDateAriaLabel()"
                  @pointerenter="showPeakDayTooltip($event)"
                  @pointermove="tt.move($event)"
                  @pointerleave="tt.hide()"
                  @focus="showPeakDayTooltip($event)"
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
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.005em;
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
    --comb-chrome: 134px;
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
    max-width: calc((100dvh - var(--comb-reserved) - var(--comb-chrome)) * 3.73);
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
    grid-auto-rows: 1fr;
    gap: 10px;
    min-height: 0;
  }

  .kpi-grid :deep(.stat-tile) {
    align-items: center;
    justify-content: center;
    text-align: center;
  }

  .kpi-grid :deep(.meta) {
    justify-content: center;
  }

  /* Only the percentage carries the trend colour; the button reset keeps the rest muted. */
  .kpi-meta-button {
    appearance: none;
    background: transparent;
    border: none;
    padding: 0;
    color: var(--text-muted);
    font: inherit;
  }
  .kpi-meta-button.trend-up .trend-pct {
    color: var(--ok);
  }
  .kpi-meta-button.trend-down .trend-pct {
    color: var(--bad);
  }
  .kpi-meta-button {
    cursor: pointer;
    transition: opacity var(--motion-fast);
  }
  .kpi-meta-button:hover {
    opacity: 0.8;
  }
  .kpi-meta-button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-radius: 2px;
  }

  .daily-card,
  .readings-card {
    min-height: 0;
  }

  .readings-notes {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    justify-content: center;
  }

  .readings-notes :deep(.insight) {
    padding: 8px 12px;
    line-height: 1.45;
    align-items: center;
    text-align: left;
  }

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

    .country-select {
      flex: 1 1 100%;
    }

    .bottom-row {
      display: flex;
      flex-direction: column;
    }

    .kpi-grid {
      grid-template-columns: 1fr 1fr;
    }

    /* The card had a min-height but nothing stretched the chart into it, so the
       svg collapsed to ~60px and the bars were unreadable. Make the flex chain
       reach the svg and give it a legible floor of its own. */
    .daily-card {
      min-height: 260px;
    }

    .daily-card :deep(.daily-columns) {
      flex: 1;
    }

    .daily-card :deep(.daily-figure svg) {
      min-height: 170px;
    }
  }
</style>
