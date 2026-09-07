<script setup lang="ts">
  import { computed, onUnmounted, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useQuery } from '@tanstack/vue-query'
  import { listSessionsOptions } from '@/api/generated/@tanstack/vue-query.gen'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { useReducedMotion } from '@/composables/useReducedMotion'

  const emit = defineEmits<{ arrive: [payload: { a2: string; lat: number | null; lon: number | null }] }>()

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
    return d.toLocaleTimeString('en-GB', { hour12: false, timeZone: 'UTC' })
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
        <span class="res" :class="r.ok ? 'ok' : 'no'" :aria-label="r.ok ? 'accepted' : 'rejected'">{{
          r.ok ? '+' : 'x'
        }}</span>
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
    box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.6);
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
      box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.55);
    }
    70% {
      box-shadow: 0 0 0 9px rgba(245, 158, 11, 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(245, 158, 11, 0);
    }
  }

  .feed-rows {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .feed-row {
    appearance: none;
    border: none;
    background: none;
    width: 100%;
    font: inherit;
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
    background: rgba(255, 255, 255, 0.03);
  }
  .feed-row:focus-visible {
    outline: 1px solid var(--accent);
    outline-offset: -1px;
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
    .feed {
      left: 12px;
      right: 12px;
      bottom: 12px;
      width: auto;
    }
  }


</style>
