<script setup lang="ts">
  import { computed, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
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
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import StatTile from '@/components/base/StatTile.vue'
  import WorldMap from '@/components/map/WorldMap.vue'
  import CountryDrawer from '@/components/map/CountryDrawer.vue'
  import LiveFeed from '@/components/map/LiveFeed.vue'
  import { fmtNumber, fmtDelta } from '@/utils/format'
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

  await Promise.all([
    mapQ.suspense(),
    totalsQ.suspense(),
    trendQ.suspense(),
    activityQ.suspense(),
    authQ.suspense(),
  ])

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

  const tt = useHwTooltip()
  type Pt = { clientX?: number; clientY?: number }
  function showTip(e: Pt, title: string, rows: [string, string, ('pos' | 'neg')?][]): void {
    tt.show(title, rows)
    if (e.clientX !== undefined && e.clientY !== undefined) {
      tt.move({ clientX: e.clientX, clientY: e.clientY })
    }
  }

  const INFO = {
    sessions: {
      title: 'Sessions',
      text: 'One session is one visit to the honeypot, from connecting to leaving.',
    },
    logins: {
      title: 'Login attempts',
      text: 'Every username and password tried, across all sessions. One session can try many.',
    },
    ips: {
      title: 'Unique IPs',
      text: 'How many different addresses attacked, not how many times they connected.',
    },
  }
  type InfoKey = keyof typeof INFO
  const infoLabel = (k: InfoKey): string => `${INFO[k].title}: ${INFO[k].text}`
  const showInfo = (k: InfoKey): void => showTip({}, INFO[k].title, [['', INFO[k].text]])

  function showTrendTooltip(e: Pt): void {
    const t = trend.value
    showTip(e, '7-day trend', [
      ['This week', fmtNumber(t?.current ?? 0)],
      ['Prior week', fmtNumber(t?.previous ?? 0)],
      [
        'Change',
        t ? fmtDelta({ delta: t.delta, pct_change: t.pct_change }) : 'no data',
        t && t.delta > 0 ? 'pos' : t && t.delta < 0 ? 'neg' : undefined,
      ],
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

  // The stat group only scrolls (and so needs a tab stop) in the mobile row layout.
  const kpisScroll = ref(false)
  let kpisMql: MediaQueryList | null = null
  const syncKpis = (): void => {
    kpisScroll.value = !!kpisMql?.matches
  }

  // LiveFeed detects new rows; WorldMap owns the SVG to animate arcs
  const mapRef = useTemplateRef('map')
  function onArrive(payload: { a2: string; lat: number | null; lon: number | null }): void {
    mapRef.value?.fireArc(payload.a2, payload.lat, payload.lon)
  }

  watch(mapQ.isError, (isError) => {
    if (isError) console.error('map data failed to load', mapQ.error.value)
  })

  // If detail fetch errors, drawer collapses but ?country= persists; this catches Escape in that half-open state
  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape' && selectedCountry.value) closeDrawer()
  }
  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
    kpisMql = window.matchMedia('(max-width: 900px)')
    syncKpis()
    kpisMql.addEventListener('change', syncKpis)
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
        class="kpis"
        :tabindex="kpisScroll ? 0 : undefined"
        role="group"
        aria-label="Overview stats"
      >
        <StatTile label="Sessions" glass :value="fmtNumber(totals?.total_sessions)" :spark="spark">
          <template #label-extra>
            <button
              type="button"
              class="info-btn"
              :aria-label="infoLabel('sessions')"
              @pointerenter="showInfo('sessions')"
              @pointermove="tt.move($event)"
              @pointerleave="tt.hide()"
              @focus="showInfo('sessions')"
              @blur="tt.hide()"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path :d="ICONS.info" />
              </svg>
            </button>
          </template>
          <template #meta>
            <span
              class="meta-tip"
              :class="`trend-${trendTone}`"
              role="group"
              tabindex="0"
              :aria-label="`${trendLabel}, 7-day trend: sessions this week compared with last week`"
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
        <StatTile label="Login attempts" glass :value="fmtNumber(totals?.total_auth_attempts)">
          <template #label-extra>
            <button
              type="button"
              class="info-btn"
              :aria-label="infoLabel('logins')"
              @pointerenter="showInfo('logins')"
              @pointermove="tt.move($event)"
              @pointerleave="tt.hide()"
              @focus="showInfo('logins')"
              @blur="tt.hide()"
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
              @pointerenter="showAuthTooltip($event)"
              @pointermove="tt.move($event)"
              @pointerleave="tt.hide()"
              @focus="showAuthTooltip({})"
              @blur="tt.hide()"
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
              @pointerenter="showInfo('ips')"
              @pointermove="tt.move($event)"
              @pointerleave="tt.hide()"
              @focus="showInfo('ips')"
              @blur="tt.hide()"
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
              @pointerenter="showCountriesTooltip($event)"
              @pointermove="tt.move($event)"
              @pointerleave="tt.hide()"
              @focus="showCountriesTooltip({})"
              @blur="tt.hide()"
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
    display: flex;
    overflow: clip;
  }

  .kpis {
    position: absolute;
    z-index: 10;
    left: 22px;
    top: 76px;
    width: fit-content;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .kpis:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .kpis :deep(.stat-tile) {
    min-height: 88px;
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

  .meta-tip {
    cursor: help;
    transition: opacity var(--motion-fast);
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

  /* 24px hit area (WCAG 2.5.8) around the 16px control. */
  .info-btn::after {
    content: '';
    position: absolute;
    inset: -4px;
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
    /* Full-bleed scroller: the inset lives in the padding, not in the box, so
       the first and last tiles reach the screen edges instead of being clipped
       by a narrower scroll container. */
    .kpis {
      top: 66px;
      left: 0;
      right: 0;
      width: auto;
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
    .kpis :deep(.stat-tile) {
      min-width: 148px;
      flex: none;
      scroll-snap-align: start;
      box-shadow: none;
    }
  }
</style>
