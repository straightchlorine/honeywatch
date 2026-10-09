<script setup lang="ts">
  import { computed, onUnmounted, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useQuery } from '@tanstack/vue-query'
  import { listSessionsOptions } from '@/api/generated/@tanstack/vue-query.gen'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { useReducedMotion } from '@/composables/useReducedMotion'
  import { fmtUtcClock } from '@/utils/format'

  const emit = defineEmits<{
    arrive: [payload: { a2: string; lat: number | null; lon: number | null }]
  }>()

  const router = useRouter()
  const paused = ref(false)
  const reducedMotion = useReducedMotion()

  // 8 rows are fetched so the arc watcher sees enough churn between polls;
  // the panel only shows whole rows, capped at VISIBLE_ROWS.
  const VISIBLE_ROWS = 4

  const feedQ = useQuery(
    computed(() => ({
      ...listSessionsOptions({ query: { per_page: 8, sort: 'recent' } }),
      refetchInterval: paused.value ? false : 20_000,
      refetchIntervalInBackground: false,
    })),
  )

  interface Row {
    id: string
    time: string
    a2: string | null
    flag: string
    country: string
    label: string
    ok: boolean
    lat: number | null
    lon: number | null
  }

  function fmtClock(iso: string | null): string {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    return fmtUtcClock(d)
  }

  const rows = computed<Row[]>(
    () =>
      feedQ.data.value?.items.map((s) => {
        const countryName = s.country ?? s.country_code ?? 'Unknown'
        const location = s.city ? `${s.city}, ${countryName}` : countryName
        return {
          id: s.id,
          time: fmtClock(s.started_at),
          a2: s.country_code,
          flag: useCountryFlag(s.country_code),
          country: location,
          label: s.category === 'active' ? `${s.protocol} CLI` : `${s.protocol} ${s.category}`,
          ok: s.has_successful_login,
          lat: s.lat ?? null,
          lon: s.lon ?? null,
        }
      }) ?? [],
  )

  const statusText = computed(() => {
    if (rows.value.length) return ''
    if (feedQ.isError.value) return 'Could not load live sessions. Retrying.'
    return feedQ.isPending.value ? 'Loading sessions...' : 'No sessions yet.'
  })

  let seen = new Set<string>()
  let firstLoad = true
  // Stagger emissions over the poll interval to avoid firing all arcs in one frame.
  const ARRIVAL_STAGGER_MS = 1400
  let staggerTimers: ReturnType<typeof setTimeout>[] = []

  watch(rows, (next) => {
    if (firstLoad) {
      seen = new Set(next.map((r) => r.id))
      firstLoad = false
      return
    }
    if (reducedMotion.value) return
    const fresh = next.filter((r) => !seen.has(r.id) && r.a2)
    seen = new Set(next.map((r) => r.id))

    staggerTimers.forEach(clearTimeout)
    staggerTimers = []
    fresh.forEach((r, i) => {
      const fire = () => emit('arrive', { a2: r.a2 as string, lat: r.lat, lon: r.lon })
      if (i === 0) fire()
      else staggerTimers.push(setTimeout(fire, i * ARRIVAL_STAGGER_MS))
    })
  })

  onUnmounted(() => staggerTimers.forEach(clearTimeout))

  function openSession(id: string): void {
    router.push({ name: 'sessions', query: { open: id, sort: 'recent' } })
  }

  function togglePause(): void {
    paused.value = !paused.value
  }
</script>

<template>
  <div class="feed glass" aria-live="off">
    <h2>
      <span class="live-dot" :class="{ paused }" aria-hidden="true" />
      Live sessions
      <!-- WCAG 2.2.2 (Pause, Stop, Hide). -->
      <button
        type="button"
        class="pause-btn"
        :aria-pressed="paused"
        :aria-label="paused ? 'Resume live session updates' : 'Pause live session updates'"
        @click="togglePause"
      >
        {{ paused ? 'Resume' : 'Pause' }}
      </button>
    </h2>
    <div class="feed-rows">
      <!-- Always mounted: a live region announces text changes, not nodes inserted with their text. -->
      <p class="feed-empty" role="status">{{ statusText }}</p>
      <button
        v-for="r in rows.slice(0, VISIBLE_ROWS)"
        :key="r.id"
        type="button"
        class="feed-row"
        :aria-label="`Open session from ${r.country} at ${r.time}, ${r.ok ? 'accepted' : 'rejected'}`"
        @click="openSession(r.id)"
      >
        <span class="t">{{ r.time }}</span>
        <span aria-hidden="true">{{ r.flag }}</span>
        <span class="country">{{ r.country }}</span>
        <span class="label">{{ r.label }}</span>
        <span
          class="res"
          :class="r.ok ? 'ok' : 'no'"
          :aria-label="r.ok ? 'accepted' : 'rejected'"
          >{{ r.ok ? '+' : 'x' }}</span
        >
      </button>
    </div>
  </div>
</template>

<style scoped>
  .feed {
    position: absolute;
    z-index: 10;
    left: 22px;
    bottom: 22px;
    width: 460px;
    border-radius: var(--radius-lg);
    padding: 10px 14px 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .feed h2 {
    margin: 0 0 6px;
    font: 650 10.5px var(--font-sans);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-dim);
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .live-dot.paused {
    animation: none;
    background: var(--text-dim);
  }

  .live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 60%, transparent);
    animation: live-pulse 2.4s ease-out infinite;
  }

  .pause-btn {
    margin-left: auto;
    flex: none;
    min-height: 24px;
    padding: 3px 10px;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--text-muted);
    font: 650 10px var(--font-sans);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
    transition:
      color var(--motion-fast),
      border-color var(--motion-fast);
  }

  .pause-btn:hover,
  .pause-btn:focus-visible {
    color: var(--text);
    border-color: var(--accent-dim);
  }

  .pause-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  @keyframes live-pulse {
    0% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 55%, transparent);
    }
    70% {
      box-shadow: 0 0 0 9px color-mix(in srgb, var(--accent) 0%, transparent);
    }
    100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 0%, transparent);
    }
  }

  .feed-rows {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-height: 4.5rem;
  }

  .feed-empty {
    margin: 0;
    padding: 4px 2px;
    font: 500 11.5px var(--font-mono);
    color: var(--text-dim);
  }

  /* Kept in the DOM while empty (see template) but must not take up a row. */
  .feed-empty:empty {
    padding: 0;
  }

  .feed-row {
    appearance: none;
    border: none;
    background: none;
    width: 100%;
    text-align: left;
    display: grid;
    grid-template-columns: 58px 20px minmax(90px, 1fr) minmax(120px, 1.2fr) 20px;
    gap: 8px;
    align-items: center;
    font: 500 11.5px var(--font-mono);
    color: var(--text-muted);
    padding: 4px 2px;
    border-radius: 4px;
    cursor: pointer;
  }
  .feed-row:hover {
    background: var(--surface-hover);
  }
  .feed-row:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  .feed-row .t {
    color: var(--text-dim);
  }
  .feed-row .country {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .feed-row .label {
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .feed-row .res.ok {
    color: var(--ok);
  }
  .feed-row .res.no {
    color: var(--bad);
  }

  @media (max-width: 900px) {
    /* Raised to clear the map controls, which sit centred below it on mobile. */
    .feed {
      left: 12px;
      right: 12px;
      bottom: 62px;
      width: auto;
      background: color-mix(in srgb, var(--surface, #14110c) 88%, transparent);
    }
    .feed-row {
      grid-template-columns: 50px 18px minmax(110px, 1.4fr) minmax(70px, 0.9fr) 16px;
      gap: 6px;
    }
  }
</style>
