<script setup lang="ts">
  import { computed, nextTick, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useQuery } from '@tanstack/vue-query'
  import {
    statsMapOptions,
    statsCountryDetailOptions,
    statsTotalsOptions,
    statsTrendOptions,
    statsActivityOptions,
    statsAuthOutcomesOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import { suspenseAll } from '@/api/queries'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import StatTile from '@/components/base/StatTile.vue'
  import WorldMap from '@/components/map/WorldMap.vue'
  import CountryDrawer from '@/components/map/CountryDrawer.vue'
  import LiveFeed from '@/components/map/LiveFeed.vue'
  import { fmtNumber, fmtCompact, fmtDelta, fmtDeltaParts } from '@/utils/format'
  import { WORLD_COUNTRY_COUNT } from '@/utils/countries'
  import { ICONS } from '@/components/icons'

  const route = useRoute()
  const router = useRouter()

  const selectedCountry = computed(() => {
    const q = route.query.country
    return typeof q === 'string' && q ? q.toUpperCase() : null
  })

  // DrawerShell owns focus management (WCAG 2.4.3); this drives URL/selection and city-focus side effect
  function selectCountry(a2: string): void {
    void router.replace({ query: { ...route.query, country: a2 } })
    // A focused city from the previous country's drawer would be stale/
    // confusing once the drawer switches to a different country's data.
    if (a2 !== selectedCountry.value) mapRef.value?.clearCityFocus()
  }

  function closeDrawer(): void {
    const rest = { ...route.query }
    delete rest.country
    void router.replace({ query: rest })
    mapRef.value?.clearCityFocus()
  }

  const POLL_MS = 120_000
  const mapQ = useQuery({ ...statsMapOptions(), refetchInterval: POLL_MS })
  const totalsQ = useQuery({ ...statsTotalsOptions(), refetchInterval: POLL_MS })
  const trendQ = useQuery({
    ...statsTrendOptions({ query: { period_days: 7 } }),
    refetchInterval: POLL_MS,
  })
  const activityQ = useQuery({
    ...statsActivityOptions({ query: { bucket: 'day' } }),
    refetchInterval: POLL_MS,
  })
  const authQ = useQuery({ ...statsAuthOutcomesOptions(), refetchInterval: POLL_MS })

  const countryQ = useQuery(
    computed(() => ({
      ...statsCountryDetailOptions({ path: { a2: selectedCountry.value ?? '' } }),
      enabled: !!selectedCountry.value,
    })),
  )
  // `isPending` stays true for a disabled query (no fetch has ever run), so it
  // alone can't drive the drawer's loading state - gate it on a selection too.
  const countryLoading = computed(() => !!selectedCountry.value && countryQ.isPending.value)

  await suspenseAll(mapQ, totalsQ, trendQ, activityQ, authQ)

  const countries = computed(() => mapQ.data.value?.countries ?? [])
  const cities = computed(() => mapQ.data.value?.cities ?? [])
  const totals = computed(() => totalsQ.data.value)
  const trend = computed(() => trendQ.data.value)
  const spark = computed(() => {
    const vals = (activityQ.data.value ?? []).slice(-7).map((b) => b.count)
    return vals.length > 1 ? vals : [0, 0]
  })
  const acceptedPct = computed(() => {
    const r = authQ.data.value?.success_rate
    return r === null || r === undefined ? 'no data' : `${r.toFixed(2)}% accepted`
  })
  const trendTone = computed<'up' | 'down' | 'neutral'>(() => {
    if (!trend.value) return 'neutral'
    if (trend.value.delta > 0) return 'up'
    if (trend.value.delta < 0) return 'down'
    return 'neutral'
  })
  const trendLabel = computed(() =>
    trend.value ? fmtDelta({ delta: trend.value.delta, pct_change: trend.value.pct_change }) : '',
  )
  // Tile line: this week's count, then only the percentage (the delta when there is no percentage).
  const trendPct = computed(() => {
    const p = trend.value ? fmtDeltaParts(trend.value) : null
    return p ? (p.pct ?? p.abs) : ''
  })

  const tt = useHwTooltip()
  type Pt = { clientX?: number; clientY?: number; currentTarget?: EventTarget | null }
  function showTip(e: Pt, title: string, rows: [string, string, ('pos' | 'neg')?][]): void {
    // Focus and touch-tap carry no pointer coordinates: anchor to the element instead.
    if (e.clientX === undefined && e.currentTarget instanceof Element) {
      tt.showAt(e.currentTarget, title, rows)
    } else tt.show(title, rows, undefined, e)
  }

  const INFO = {
    sessions: {
      title: 'Sessions',
      text: 'One session is one visit to the honeypot, from connecting to leaving. Below: sessions this week, and the change from the week before.',
    },
    logins: {
      title: 'Logins',
      text: 'Every username and password tried, across all sessions. One session can try many.',
    },
    ips: {
      title: 'Unique IPs',
      text: 'How many different addresses attacked, not how many times they connected.',
    },
  }
  type InfoKey = keyof typeof INFO
  const infoLabel = (k: InfoKey): string => `${INFO[k].title}: ${INFO[k].text}`
  const showInfo = (k: InfoKey, e: Event): void => showTip(e, INFO[k].title, [['', INFO[k].text]])

  // Hover and focus open the same tip; Escape closes it.
  function tipEvents(show: (e: Event) => void) {
    return {
      pointerenter: show,
      pointermove: (e: PointerEvent) => tt.move(e),
      pointerleave: () => tt.hide(),
      focus: show,
      blur: () => tt.hide(),
      keydown: (e: KeyboardEvent) => {
        if (e.key === 'Escape') tt.hide()
      },
    }
  }

  function showTrendTooltip(e: Pt): void {
    const t = trend.value
    const tone = trendTone.value === 'up' ? 'pos' : trendTone.value === 'down' ? 'neg' : undefined
    showTip(e, '7-day trend', [
      ['This week', fmtNumber(t?.current ?? 0)],
      ['Prior week', fmtNumber(t?.previous ?? 0)],
      ['Change', t ? fmtDelta({ delta: t.delta, pct_change: t.pct_change }) : 'no data', tone],
    ])
  }

  function showAuthTooltip(e: Pt): void {
    const authData = authQ.data.value
    const acceptedCount = fmtNumber(authData?.successful ?? 0)
    const totalCount = fmtNumber(authData?.total ?? 0)
    showTip(e, 'Login success rate', [['Accepted', `${acceptedCount} of ${totalCount}`]])
  }

  function showCountriesTooltip(e: Pt): void {
    showTip(e, 'Share of all countries', [
      [
        '',
        `${((countries.value.length / WORLD_COUNTRY_COUNT) * 100).toFixed(1)}% of ${WORLD_COUNTRY_COUNT} countries`,
      ],
    ])
  }

  // The stat group only scrolls (and so needs a tab stop) in the phone row layout.
  const kpisScroll = ref(false)
  let kpisMql: MediaQueryList | null = null
  const syncKpis = (): void => {
    kpisScroll.value = !!kpisMql?.matches
  }

  // Phone row opens on the middle tile; re-centred when the numbers land, until the user scrolls.
  const kpisEl = useTemplateRef<HTMLElement>('kpis')
  let kpisTouched = false
  function touchKpis(): void {
    kpisTouched = true
  }
  function centerKpis(): void {
    const el = kpisEl.value
    const mid = el?.querySelector<HTMLElement>('.tile-sessions')
    if (!el || !mid || !kpisMql?.matches || kpisTouched) return
    el.style.scrollSnapType = 'none'
    el.scrollLeft = mid.offsetLeft - (el.clientWidth - mid.offsetWidth) / 2
    el.style.scrollSnapType = ''
  }
  watch(totalsQ.dataUpdatedAt, () => nextTick(centerKpis))

  // LiveFeed detects new rows; WorldMap owns the SVG to animate arcs
  const mapRef = useTemplateRef('map')
  function onArrive(payload: { a2: string; lat: number | null; lon: number | null }): void {
    mapRef.value?.fireArc(payload.a2, payload.lat, payload.lon)
  }

  watch(mapQ.isError, (isError) => {
    if (isError) console.error('map data failed to load', mapQ.error.value)
  })

  // ?country= persists after a failed detail fetch (the drawer then shows only an error); Escape must still close it
  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape' && selectedCountry.value) closeDrawer()
  }
  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
    if (typeof window.matchMedia === 'function') {
      kpisMql = window.matchMedia('(max-width: 900px)')
      syncKpis()
      kpisMql.addEventListener('change', syncKpis)
    }
    centerKpis()
  })
  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
    kpisMql?.removeEventListener('change', syncKpis)
  })
</script>

<template>
  <PageShell full-bleed>
    <template #head>
      <TopBar current="overview" overlay />
    </template>

    <div class="overview">
      <h1 class="visually-hidden">Overview</h1>
      <WorldMap
        ref="map"
        :countries="countries"
        :cities="cities"
        :selected="selectedCountry"
        :total-sessions="totals?.total_sessions ?? 0"
        @select="selectCountry"
        @deselect="closeDrawer"
      />

      <div
        ref="kpis"
        class="kpis"
        @pointerdown.passive="touchKpis"
        @wheel.passive="touchKpis"
        :tabindex="kpisScroll ? 0 : undefined"
        role="group"
        aria-label="Overview stats"
      >
        <StatTile
          class="tile-sessions"
          label="Sessions"
          glass
          :value="fmtNumber(totals?.total_sessions)"
          :spark="spark"
        >
          <template #label-extra>
            <button
              type="button"
              class="info-btn"
              :aria-label="infoLabel('sessions')"
              v-on="tipEvents((e) => showInfo('sessions', e))"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path :d="ICONS.info" />
              </svg>
            </button>
          </template>
          <template #meta>
            <span
              class="meta-tip trend-tip"
              :class="`trend-${trendTone}`"
              role="group"
              tabindex="0"
              :aria-label="`${fmtCompact(trend?.current)} sessions this week, ${trendLabel} vs prior week`"
              v-on="tipEvents(showTrendTooltip)"
            >
              <span class="trend-count">{{ fmtCompact(trend?.current) }}</span>
              <span class="trend-dot" aria-hidden="true">&middot;</span>
              <span class="trend-pct">{{ trendPct }}</span>
            </span>
          </template>
        </StatTile>
        <StatTile
          class="tile-login"
          label="Logins"
          glass
          :value="fmtNumber(totals?.total_auth_attempts)"
        >
          <template #label-extra>
            <button
              type="button"
              class="info-btn"
              :aria-label="infoLabel('logins')"
              v-on="tipEvents((e) => showInfo('logins', e))"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path :d="ICONS.info" />
              </svg>
            </button>
          </template>
          <template #meta>
            <span
              class="meta-tip"
              role="group"
              tabindex="0"
              :aria-label="`${acceptedPct}, login success rate: accepted logins out of total attempts`"
              v-on="tipEvents(showAuthTooltip)"
            >
              {{ acceptedPct }}
            </span>
          </template>
        </StatTile>
        <StatTile label="Unique IPs" glass :value="fmtNumber(totals?.unique_ips)">
          <template #label-extra>
            <button
              type="button"
              class="info-btn"
              :aria-label="infoLabel('ips')"
              v-on="tipEvents((e) => showInfo('ips', e))"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path :d="ICONS.info" />
              </svg>
            </button>
          </template>
          <template #meta>
            <span
              class="meta-tip"
              role="group"
              tabindex="0"
              :aria-label="`${countries.length} countries, share of the world represented`"
              v-on="tipEvents(showCountriesTooltip)"
            >
              {{ countries.length }} countries
            </span>
          </template>
        </StatTile>
      </div>

      <LiveFeed @arrive="onArrive" />

      <CountryDrawer
        :detail="countryQ.data.value ?? null"
        :loading="countryLoading"
        :failed="!!selectedCountry && countryQ.isError.value && !countryQ.data.value"
        @close="closeDrawer"
        @fly-to-city="
          (p) =>
            mapRef?.flyToCity(p.lat, p.lon, {
              city: p.city,
              country_code: p.country_code,
              sessions: p.sessions,
            })
        "
      />
    </div>
  </PageShell>
</template>

<style scoped>
  .overview {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    --hud-gap: 12px;
    --hud-ctl-h: 32px;
    display: flex;
    overflow: clip;
  }

  .kpis {
    position: absolute;
    z-index: 10;
    left: 22px;
    top: 76px;
    width: fit-content;
    display: grid;
    gap: 10px;
  }

  .trend-up .trend-pct {
    color: var(--ok);
  }
  .trend-down .trend-pct {
    color: var(--bad);
  }

  .kpis :deep(.stat-tile) {
    text-align: center;
    position: relative;
  }
  .kpis :deep(.spark) {
    order: 3;
  }
  .kpis :deep(.meta) {
    order: 4;
    justify-content: center;
  }
  /* Header line: label top-left, info dot pinned top-right on the same line (one line,
     so the label can size the tile when numbers are short). */
  .kpis :deep(.label-row) {
    contain: none;
    text-align: left;
    padding-right: 22px;
  }
  .kpis :deep(.label) {
    white-space: nowrap;
  }
  .kpis :deep(.tail button) {
    position: absolute;
    top: 11px;
    right: 16px;
    margin: 0;
  }
  .kpis :deep(.stat-tile:not(:has(.spark)) .meta) {
    flex: 1;
    align-items: center;
  }
  .meta-tip {
    flex: none;
    min-width: 0;
    cursor: help;
    transition: opacity var(--motion-fast);
  }
  /* Touch: 44px hit area, visuals unchanged. */
  @media (pointer: coarse) {
    .meta-tip {
      position: relative;
    }
    .meta-tip::after {
      content: '';
      position: absolute;
      inset: -16px 0;
    }
  }

  .trend-dot {
    padding: 0 6px;
  }

  .meta-tip:hover {
    opacity: 0.8;
  }
  .meta-tip:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-radius: 2px;
  }

  .info-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 0.25rem;
    color: var(--text-muted);
    cursor: pointer;
    transition:
      color var(--motion-fast),
      background var(--motion-fast);
    flex-shrink: 0;
    position: relative;
  }

  /* 24px hit area (WCAG 2.5.8) around the 16px control; 44px on touch. */
  .info-btn::after {
    content: '';
    position: absolute;
    inset: -4px;
  }

  @media (pointer: coarse) {
    .info-btn::after {
      inset: -14px;
    }
  }

  .info-btn:hover {
    color: var(--text);
    background: var(--surface-hover);
  }

  .info-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-radius: 2px;
  }

  .info-btn svg {
    width: 0.75rem;
    height: 0.75rem;
    fill: currentColor;
  }

  @media (max-width: 900px) {
    /* Swipeable row; tiles grow with their numbers. Spark sits above the meta so a
       caption-only tile centres its meta in the same band. */
    .kpis {
      top: 66px;
      left: 0;
      right: 0;
      width: auto;
      display: flex;
      flex-direction: row;
      overflow-x: auto;
      overscroll-behavior-x: contain;
      scrollbar-width: none;
      padding: 0 12px 4px;
      scroll-padding-inline: 12px;
      scroll-snap-type: x proximity;
    }
    .kpis::-webkit-scrollbar {
      display: none;
    }
    .kpis:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: -2px;
    }
    .kpis :deep(.stat-tile) {
      flex: none;
      min-width: 148px;
      scroll-snap-align: center;
      box-shadow: none;
    }
    /* DOM is Sessions-first (desktop stack); phones show Logins first. Tab order follows the DOM. */
    .kpis :deep(.tile-login) {
      order: -1;
    }
  }
</style>
