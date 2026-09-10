<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import type { StatsCountryDetailResponse, MapCityResponse } from '@/api/generated/types.gen'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { fmtNumber } from '@/utils/format'
  import { cleanCred, fmtSuccessRate } from '@/utils/credentials'
  import { ICONS } from '@/components/icons'
  import InfoDot from '@/components/base/InfoDot.vue'
  import RankList, { type RankRow } from '../base/RankList.vue'
  import Sparkline from '../charts/Sparkline.vue'
  import RoundedButton from '../base/RoundedButton.vue'
  import TransparentButton from '../base/TransparentButton.vue'
  import DrawerShell from '../base/DrawerShell.vue'

  const {
    detail,
    loading = false,
    showFullIntel = true,
  } = defineProps<{
    detail: StatsCountryDetailResponse | null
    loading?: boolean
    /** "Full details" links to Origins - hide it when already on that page. */
    showFullIntel?: boolean
  }>()
  const emit = defineEmits<{
    close: []
    'fly-to-city': [payload: { lat: number; lon: number; city?: string; country_code?: string; sessions?: number }]
  }>()

  const flag = computed(() => (detail ? useCountryFlag(detail.a2) : ''))

  const dailyValues = computed(() => {
    const vals = detail?.daily.map((d) => d.sessions) ?? []
    return vals.length ? vals : [0, 0]
  })

  const asnRows = computed<RankRow[]>(() => {
    const items = detail?.top_asns ?? []
    const max = items.reduce((m, a) => Math.max(m, a.sessions), 0) || 1
    return items.map((a) => {
      return {
        label: a.as_org ?? (a.asn !== null ? `AS${a.asn}` : 'Unknown network'),
        title: [
          a.as_org ?? 'Unknown network',
          `${fmtNumber(a.sessions)} sessions`,
        ].join(' - '),
        value: fmtNumber(a.sessions),
        frac: a.sessions / max,
        mono: false,
      }
    })
  })

  const credRows = computed<RankRow[]>(() => {
    const items = detail?.top_credentials ?? []
    const max = items.reduce((m, c) => Math.max(m, c.count), 0) || 1
    return items.map((c) => ({
      label: `${cleanCred(c.username ?? '') || '(blank)'}:${cleanCred(c.password ?? '') || '(blank)'}`,
      value: fmtNumber(c.count),
      frac: c.count / max,
      mono: true,
    }))
  })

  const tt = useHwTooltip()
  const selectedCityKey = ref<string | null>(null)
  function cityKey(city: MapCityResponse): string {
    return `${city.country_code}-${city.city}`
  }
  function handleCityClick(city: MapCityResponse): void {
    selectedCityKey.value = cityKey(city)
    emit('fly-to-city', {
      lat: city.lat,
      lon: city.lon,
      city: city.city,
      country_code: city.country_code,
      sessions: city.sessions,
    })
  }
  // A new country's list shouldn't keep a highlight from the previous one.
  watch(
    () => detail?.a2,
    () => {
      selectedCityKey.value = null
    },
  )
  function showCityTooltip(e: { clientX?: number; clientY?: number }, city: MapCityResponse): void {
    tt.show('Location', [
      ['Coordinates', `${city.lat.toFixed(2)}, ${city.lon.toFixed(2)}`],
      ['Sessions', fmtNumber(city.sessions)],
    ])
    if (e.clientX !== undefined && e.clientY !== undefined) {
      tt.move({ clientX: e.clientX, clientY: e.clientY })
    }
  }

  function getSuccessfulCount(): number {
    if (!detail || detail.success_rate === null) return 0
    // Derived approximation: success_rate is a percentage, so convert to count
    return Math.round((detail.success_rate / 100) * detail.attempts)
  }

  function showSuccessTooltip(e: { clientX?: number; clientY?: number }): void {
    const successful = getSuccessfulCount()
    tt.show('Accepted', [['Attempts', `${fmtNumber(successful)} of ${fmtNumber(detail?.attempts ?? 0)} accepted`]])
    if (e.clientX !== undefined && e.clientY !== undefined) {
      tt.move({ clientX: e.clientX, clientY: e.clientY })
    }
  }

</script>

<template>
  <DrawerShell
    :open="!!detail || loading"
    :title="detail?.name ?? 'Loading...'"
    @close="emit('close')"
  >
    <template #head-extra>
      <span v-if="detail" class="fl" aria-hidden="true">{{ flag }}</span>
    </template>

    <template v-if="detail">
      <div class="d-hero">
        <span class="n">{{ fmtNumber(detail.sessions) }}</span>
        <span class="l">Sessions<br />all time</span>
      </div>
      <Sparkline class="sparkline-animate" :values="dailyValues" :w="340" :h="44" color="var(--accent-strong)" />
      <div class="d-grid">
        <div><span class="k">Attempts</span><span class="v">{{ fmtNumber(detail.attempts) }}</span></div>
        <div><span class="k">Unique IPs</span><span class="v">{{ fmtNumber(detail.ips) }}</span></div>
        <div
          role="button"
          tabindex="0"
          @pointerenter="showSuccessTooltip($event)"
          @pointermove="tt.move($event)"
          @pointerleave="tt.hide()"
          @focus="showSuccessTooltip({})"
          @blur="tt.hide()"
          @keydown.enter="showSuccessTooltip({})"
          @keydown.space.prevent="showSuccessTooltip({})"
        >
          <span class="k">Success</span>
          <span class="v">{{ fmtSuccessRate(detail.success_rate) }}</span>
        </div>
      </div>
      <div class="heading-with-info">
        <h3>Top networks</h3>
        <InfoDot
          title="Top networks"
          text="The internet providers attackers from this country use most."
        />
      </div>
      <RankList v-if="asnRows.length" :rows="asnRows" label-width="140px" />
      <p v-else class="empty">No networks recorded.</p>
      <div class="heading-with-info">
        <h3>Top credentials tried</h3>
        <InfoDot
          title="Top credentials tried"
          text="The most common username:password combinations attackers tried from this country."
        />
      </div>
      <RankList v-if="credRows.length" :rows="credRows" label-width="140px" mono />
      <p v-else class="empty">No login attempts recorded.</p>
      <div class="heading-with-info">
        <h3>Top cities</h3>
        <InfoDot
          title="Top cities"
          text="The busiest cities in this country by session count - click one to locate it on the map."
        />
      </div>
      <ul v-if="detail.top_cities.length" class="cities-list">
        <li v-for="(city, idx) in detail.top_cities" :key="cityKey(city)">
          <button
            type="button"
            class="city-row"
            :class="{ selected: selectedCityKey === cityKey(city) }"
            :style="{ '--city-weight': city.sessions / (detail.top_cities[0]?.sessions ?? 1) }"
            @click="handleCityClick(city)"
            @pointerenter="showCityTooltip($event, city)"
            @pointermove="tt.move($event)"
            @pointerleave="tt.hide()"
            @focus="showCityTooltip({}, city)"
            @blur="tt.hide()"
          >
            <span class="city-rank">{{ idx + 1 }}</span>
            <span class="city-name">{{ city.city }}</span>
            <span class="city-count">{{ fmtNumber(city.sessions) }}</span>
          </button>
        </li>
      </ul>
      <p v-else class="empty">No cities recorded.</p>
      <div class="foot">
        <RoundedButton :to="{ name: 'sessions', query: { country: detail.a2 } }">
          Sessions from {{ detail.a2 }}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display: block">
            <path :d="ICONS['chevron-right']" fill="currentColor" />
          </svg>
        </RoundedButton>
        <TransparentButton
          v-if="showFullIntel"
          :to="{ name: 'origins', query: { country: detail.a2 } }"
        >
          Full details
        </TransparentButton>
      </div>
    </template>
    <div v-else-if="loading" class="d-loading" role="status">Loading...</div>
  </DrawerShell>
</template>

<style scoped>
  .fl {
    font-size: 26px;
  }

  .d-hero {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .d-hero .n {
    font-size: 40px;
    font-weight: 700;
    letter-spacing: -0.015em;
  }
  .d-hero .l {
    color: var(--text-dim);
    font-size: 12px;
  }

  .d-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
  }
  .d-grid > div {
    background: rgba(43, 32, 26, 0.6);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .d-grid .k {
    font: 600 10px var(--font-sans);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
  }
  .d-grid .v {
    font: 620 16px var(--font-sans);
    color: var(--text);
  }

  .heading-with-info {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  h3 {
    margin: 4px 0 0;
    font: 650 11px var(--font-sans);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .empty {
    margin: 0;
    font-size: 12px;
    color: var(--text-dim);
  }





  .mono {
    font-family: var(--font-mono);
    font-size: 12.5px;
  }

  .cities-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .city-row {
    appearance: none;
    border: none;
    width: 100%;
    font-family: inherit;
    text-align: left;
    display: grid;
    grid-template-columns: 24px 1fr 50px;
    gap: 8px;
    align-items: center;
    padding: 6px 8px;
    border-radius: 6px;
    background: linear-gradient(90deg, rgba(132, 204, 22, calc(0.08 * var(--city-weight))) 0%, transparent 100%);
    font-size: 12px;
    cursor: pointer;
    transition: background var(--motion-fast);
  }

  .city-row:hover {
    background: linear-gradient(90deg, rgba(132, 204, 22, calc(0.15 * var(--city-weight))) 0%, transparent 100%);
  }

  .city-row:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
    border-radius: 6px;
  }

  /* Mirrors the map's temporary focus marker. */
  .city-row.selected {
    background: linear-gradient(90deg, rgba(132, 204, 22, calc(0.22 * var(--city-weight))) 0%, transparent 100%);
    border: 1px solid var(--accent-dim);
  }

  .city-row.selected .city-name {
    color: var(--text);
    font-weight: 600;
  }

  .city-rank {
    text-align: center;
    color: var(--text-dim);
    font-size: 11px;
    font-weight: 600;
  }

  .city-name {
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .city-count {
    text-align: right;
    color: var(--text);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12px;
  }

  .foot {
    margin-top: auto;
    display: flex;
    gap: 8px;
  }
  .foot :deep(.rounded-button),
  .foot :deep(.transparent-button) {
    flex: 1;
  }

  .d-loading {
    color: var(--text-dim);
    font-size: 13px;
  }

  @keyframes drawer-fall-in {
    from {
      opacity: 0;
      transform: translateY(-8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .sparkline-animate {
    animation: drawer-fall-in 280ms ease-out both;
  }

  :deep(.rank-row) {
    animation: drawer-fall-in 280ms ease-out both;
  }

  :deep(.rank-row:nth-child(1)) {
    animation-delay: 0ms;
  }

  :deep(.rank-row:nth-child(2)) {
    animation-delay: 20ms;
  }

  :deep(.rank-row:nth-child(3)) {
    animation-delay: 40ms;
  }

  :deep(.rank-row:nth-child(4)) {
    animation-delay: 60ms;
  }

  :deep(.rank-row:nth-child(5)) {
    animation-delay: 80ms;
  }

  :deep(.rank-row:nth-child(n+6)) {
    animation-delay: 100ms;
  }

  .cities-list li {
    animation: drawer-fall-in 280ms ease-out both;
  }

  .cities-list li:nth-child(1) {
    animation-delay: 0ms;
  }

  .cities-list li:nth-child(2) {
    animation-delay: 25ms;
  }

  .cities-list li:nth-child(3) {
    animation-delay: 50ms;
  }

  .cities-list li:nth-child(4) {
    animation-delay: 75ms;
  }

  .cities-list li:nth-child(5) {
    animation-delay: 100ms;
  }

  .cities-list li:nth-child(n+6) {
    animation-delay: 125ms;
  }
</style>
