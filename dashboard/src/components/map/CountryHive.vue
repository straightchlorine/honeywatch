<script setup lang="ts">
  /**
   * Hex cartogram with one hexagon per country, shaded on the sequential amber ramp.
   * Table view toggle swaps to a plain leaderboard with fixed-height selection line
   * to prevent reflow.
   */
  import { computed, onScopeDispose, ref } from 'vue'
  import type { CountryRowResponse } from '@/api/generated/types.gen'
  import { useSeqScale, needsDarkInk } from '@/composables/useSeqScale'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { useReducedMotion } from '@/composables/useReducedMotion'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { hexPoints } from '@/utils/hex'
  import { fmtNumber, fmtCompact } from '@/utils/format'
  import { fmtSuccessRate } from '@/utils/credentials'
  import type { CountrySort } from '@/utils/countries'
  import ChipButton from '../base/ChipButton.vue'
  import SortableTh from '../base/SortableTh.vue'
  import SeqLegend from '../base/SeqLegend.vue'
  import HwCard from '../base/HwCard.vue'

  const { countries } = defineProps<{ countries: CountryRowResponse[] }>()

  const selected = defineModel<string | null>('selected', { default: null })
  const sortKey = defineModel<CountrySort>('sort', { default: 'sessions' })

  const reduced = useReducedMotion()

  const view = ref<'hive' | 'table'>('hive')

  // Hex packing: hexagon of hexagons (rows of 4/5/6/5/4) with geometry derived
  // from ROW_SIZES, so it degrades cleanly with fewer countries.
  // Mobile: show top 10 in smaller hexagon instead of shrinking 24 to unreadable labels.
  const compact = ref(false)
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    const mq = window.matchMedia('(max-width: 900px)')
    compact.value = mq.matches
    const onChange = (e: MediaQueryListEvent) => (compact.value = e.matches)
    mq.addEventListener('change', onChange)
    onScopeDispose(() => mq.removeEventListener('change', onChange))
  }

  const ROW_SIZES = computed(() => (compact.value ? [3, 4, 3] : [4, 5, 6, 5, 4]))
  const R = 46
  const HXW = Math.sqrt(3) * R
  const MAX_ROW = computed(() => Math.max(...ROW_SIZES.value))

  const CELLS = computed(() => ROW_SIZES.value.reduce((a, b) => a + b, 0))
  const top = computed(() => countries.slice(0, CELLS.value))
  const maxSessions = computed(() => {
    const sessions = top.value.map((c) => c.sessions)
    return sessions.length > 0 ? Math.max(...sessions) : 0
  })
  const minSessions = computed(() => {
    const vals = top.value.map((c) => c.sessions).filter((n) => n > 0)
    return vals.length ? Math.min(...vals) : 0
  })
  const scale = useSeqScale(maxSessions)

  // Rows actually populated by the current country list (short lists just
  // stop filling rows, they are never padded with empty cells).
  const rows = computed(() => {
    let remaining = top.value.length
    const used: number[] = []
    for (const size of ROW_SIZES.value) {
      if (remaining <= 0) break
      used.push(Math.min(size, remaining))
      remaining -= size
    }
    return used
  })

  // Half-column is split evenly by GUTTER to match card's measured aspect (1.40-1.43).
  const viewW = computed(() => HXW * (MAX_ROW.value + 0.5) + 20)
  const GUTTER = (HXW * 0.5) / 2
  const viewH = computed(() => 1.5 * R * (rows.value.length - 1) + 2 * R + 16)

  interface HexCell {
    code: string
    name: string
    cx: number
    cy: number
    fill: string
    dark: boolean
    flag: string
    sessions: number
    ips: number
    successLabel: string
    ariaLabel: string
  }

  const cells = computed<HexCell[]>(() => {
    // Flatten row index -> (row, col), each row centred under the widest row
    // via centring inset (honeycomb interlock pattern).
    const rowOf: number[] = []
    const colOf: number[] = []
    rows.value.forEach((size, row) => {
      for (let col = 0; col < size; col++) {
        rowOf.push(row)
        colOf.push(col)
      }
    })
    return top.value.map((c, i) => {
      const row = rowOf[i] ?? 0
      const col = colOf[i] ?? 0
      const size = rows.value[row] ?? 0
      const inset = ((MAX_ROW.value - size) / 2) * HXW
      const cx = 10 + GUTTER + inset + HXW * col + HXW / 2
      const cy = 8 + R + 1.5 * R * row
      const code = c.country_code ?? ''
      // Normalise across the populated range (not [0, max]) to use the full ramp;
      // 0.06 floor keeps the quietest country off the darkest stop.
      const lo = minSessions.value
      const hi = maxSessions.value
      const span = Math.log1p(hi) - Math.log1p(lo)
      const norm = span > 0 ? (Math.log1p(c.sessions) - Math.log1p(lo)) / span : 1
      const t = 0.06 + 0.94 * norm
      return {
        code,
        name: c.country ?? code,
        cx,
        cy,
        fill: scale.seq(t),
        dark: needsDarkInk(t),
        flag: useCountryFlag(code),
        sessions: c.sessions,
        ips: c.distinct_ips,
        successLabel: fmtSuccessRate(c.success_rate),
        ariaLabel: `${c.country ?? code}: ${fmtNumber(c.sessions)} sessions`,
      }
    })
  })

  // Drawn smaller than the R-spaced grid so adjacent hexes leave a visible gap.
  const R_CELL = R - 2.5
  function points(cx: number, cy: number): string {
    return hexPoints(cx, cy, R_CELL)
  }

  function cellDelay(idx: number): string {
    return reduced.value ? '0ms' : `${idx * 12}ms`
  }

  function selectCountry(code: string): void {
    if (code) selected.value = code
  }

  const tooltip = useHwTooltip()
  function onEnter(cell: HexCell, e: PointerEvent): void {
    tooltip.show(
      cell.name,
      [
        ['Sessions', fmtNumber(cell.sessions)],
        ['Unique IPs', fmtNumber(cell.ips)],
        ['Login success', cell.successLabel],
      ],
      cell.flag,
    )
    tooltip.move(e)
  }
  function onMove(e: PointerEvent): void {
    tooltip.move(e)
  }
  function onLeave(): void {
    tooltip.hide()
  }
  function onKeydown(cell: HexCell, e: KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      selectCountry(cell.code)
    }
  }
  function onRowKeydown(code: string | null, e: KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      selectCountry(code ?? '')
    }
  }

  const sortLabel = computed(() => {
    const labels: Record<CountrySort, string> = {
      sessions: 'Sessions',
      ips: 'Unique IPs',
      attempts: 'Attempts',
      success_rate: 'Success',
    }
    return labels[sortKey.value]
  })
</script>

<template>
  <HwCard class="hive-card" :title="`Top ${top.length} origins by ${sortLabel}`">
    <template #head-extra>
      <span class="toggle-row">
        <ChipButton :pressed="view === 'hive'" @toggle="view = 'hive'">Hive</ChipButton>
        <ChipButton :pressed="view === 'table'" @toggle="view = 'table'">Table</ChipButton>
      </span>
    </template>

    <!-- graphics-document allows focusable cells; role="img" forbids
         interactive descendants (axe: nested-interactive). -->
    <!-- eslint-disable vuejs-accessibility/no-static-element-interactions -->
    <svg
      v-if="view === 'hive'"
      class="hive-svg"
      role="graphics-document"
      :aria-label="`Top ${cells.length} attacking countries, shaded by session count. Switch to the table for exact figures.`"
      :viewBox="`0 0 ${viewW} ${viewH}`"
    >
      <g v-for="(cell, idx) in cells" :key="cell.code" class="hive-hex">
        <polygon
          class="hex-cell"
          :class="{ selected: cell.code === selected }"
          :points="points(cell.cx, cell.cy)"
          :fill="cell.fill"
          :style="{ animationDelay: cellDelay(idx) }"
          tabindex="0"
          role="button"
          :aria-label="cell.ariaLabel"
          @pointerenter="onEnter(cell, $event)"
          @pointermove="onMove"
          @pointerleave="onLeave"
          @click="selectCountry(cell.code)"
          @keydown="onKeydown(cell, $event)"
        />
        <text :x="cell.cx" :y="cell.cy - 12" text-anchor="middle" font-size="17">
          {{ cell.flag }}
        </text>
        <text
          :x="cell.cx"
          :y="cell.cy + 8"
          text-anchor="middle"
          font-size="12"
          font-weight="650"
          class="hex-code"
          :class="{ dark: cell.dark }"
        >
          {{ cell.code }}
        </text>
        <text
          :x="cell.cx"
          :y="cell.cy + 24"
          text-anchor="middle"
          font-size="10.5"
          class="hex-count"
          :class="{ dark: cell.dark }"
        >
          {{ fmtCompact(cell.sessions) }}
        </text>
      </g>
    </svg>

    <div v-else class="table-wrap">
      <table class="rank-table">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Country</th>
            <SortableTh v-model="sortKey" sort-key="sessions" dir="desc" class="r" hint="Sort by number of sessions">Sessions</SortableTh>
            <SortableTh v-model="sortKey" sort-key="ips" dir="desc" class="r" hint="Sort by number of unique IPs">Unique IPs</SortableTh>
            <SortableTh v-model="sortKey" sort-key="attempts" dir="desc" class="r" hint="Sort by number of login attempts">Attempts</SortableTh>
            <SortableTh v-model="sortKey" sort-key="success_rate" dir="desc" class="r" hint="Sort by login success rate">Success</SortableTh>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(c, i) in countries"
            :key="c.country_code ?? i"
            :class="{ selected: c.country_code === selected }"
            tabindex="0"
            @click="selectCountry(c.country_code ?? '')"
            @keydown="onRowKeydown(c.country_code, $event)"
          >
            <td class="num">{{ i + 1 }}</td>
            <td>{{ useCountryFlag(c.country_code) }} {{ c.country ?? c.country_code }}</td>
            <td class="r num">{{ fmtNumber(c.sessions) }}</td>
            <td class="r num">{{ fmtNumber(c.distinct_ips) }}</td>
            <td class="r num">{{ fmtNumber(c.attempts) }}</td>
            <td class="r num">{{ fmtSuccessRate(c.success_rate) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <!-- eslint-enable vuejs-accessibility/no-static-element-interactions -->

    <!-- Hint and legend only apply to hive view; hiding together avoids
         meaningless UI in table mode. -->
    <Transition name="sel">
      <div v-if="view === 'hive'" class="sel-line">
        <span class="sel-hint">Click a cell to inspect a country.</span>
        <SeqLegend class="hive-legend" :min="fmtCompact(minSessions)" :max="`${fmtCompact(maxSessions)} sessions`" />
      </div>
    </Transition>
  </HwCard>
</template>

<style scoped>
  .hive-card {
    min-height: 0;
  }

  .hive-card :deep(.card > h2) {
    flex-wrap: wrap;
  }

  /* h2's uppercase/letter-spacing are inherited by default - reset them here
     so the toggle chip labels render as typed, not tracked caps. */
  .toggle-row {
    display: flex;
    gap: 6px;
    margin-left: auto;
    text-transform: none;
    letter-spacing: normal;
  }

  .hive-svg {
    flex: 1;
    width: 100%;
  }

  .hive-svg text {
    pointer-events: none;
    font-family: var(--font-mono);
  }

  /* Contrast flip via needsDarkInk(): light ink until fill is bright, then dark.
     Use --text/--bg-1 for hierarchy via size/weight, not dimmer text that fails
     contrast earlier. */
  .hex-code,
  .hex-count {
    fill: var(--text);
  }

  .hex-code.dark,
  .hex-count.dark {
    fill: var(--bg-1);
  }

  .hex-cell {
    cursor: pointer;
    transition:
      filter var(--motion-fast),
      opacity var(--motion-fast);
    animation: hex-in 280ms ease-out both;
  }

  .hex-cell:hover {
    filter: brightness(1.15);
  }

  .hex-cell:focus {
    outline: none;
  }

  .hex-cell:focus-visible,
  .hex-cell.selected {
    stroke: var(--seq-7);
    stroke-width: 2;
  }

  .table-wrap {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border-strong) transparent;
  }

  .rank-table {
    width: 100%;
    min-width: 480px;
    border-collapse: collapse;
    font-size: 13px;
  }

  .rank-table th {
    text-align: left;
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-dim);
    padding: 8px 10px;
    border-bottom: 1px solid var(--border-strong);
    position: sticky;
    top: 0;
    background: var(--surface);
    z-index: 1;
  }

  .rank-table td {
    padding: 7px 10px;
    border-bottom: 1px solid var(--grid-line);
    vertical-align: middle;
  }

  .rank-table tbody tr {
    cursor: pointer;
    transition: background var(--motion-fast);
  }

  .rank-table tbody tr:hover {
    background: var(--surface-hover);
  }

  .rank-table tbody tr:focus {
    outline: none;
  }

  .rank-table tbody tr:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: -2px;
  }

  .rank-table tbody tr.selected {
    background: var(--surface-2);
  }

  .rank-table td.r,
  .rank-table th.r {
    text-align: right;
  }

  .rank-table .num {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12.5px;
  }

  /* min shown is the quietest populated country, not literal 1. */
  .hive-legend {
    margin-left: auto;
    flex: none;
  }

  .sel-hint {
    min-width: 0;
  }

  .sel-enter-active,
  .sel-leave-active {
    transition:
      height var(--motion-base) ease,
      margin-top var(--motion-base) ease,
      opacity var(--motion-fast) ease;
    overflow: hidden;
  }

  /* Qualified with .sel-line to win specificity: later .sel-line rule
     (height: 40px) would override bare .sel-leave-to otherwise. */
  .sel-line.sel-enter-from,
  .sel-line.sel-leave-to {
    height: 0;
    margin-top: 0;
    opacity: 0;
  }

  @media (prefers-reduced-motion: reduce) {
    .sel-enter-active,
    .sel-leave-active {
      transition: none;
    }
  }

  .sel-line {
    display: flex;
    gap: 14px;
    align-items: center;
    margin-top: 8px;
    padding: 0 13px;
    border-radius: var(--radius-md);
    background: var(--surface-2);
    border: 1px solid var(--border);
    font-size: 12.5px;
    color: var(--text-muted);
    height: 40px;
    flex: none;
    white-space: nowrap;
    overflow: hidden;
  }

  .sel-line b {
    color: var(--text);
    font-weight: 640;
  }


  .sel-line a {
    margin-left: auto;
    font-size: 12px;
    font-weight: 600;
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .arrow-icon {
    width: 12px;
    height: 12px;
    flex: none;
  }

  @keyframes hex-in {
    from {
      opacity: 0;
      transform: scale(0.85);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .hex-cell {
      animation: none;
    }
  }

  @media (max-width: 900px) {
    .hive-svg {
      min-height: 260px;
    }

    .sel-line {
      font-size: 11.5px;
      gap: 10px;
    }

    /* Legend stays; hint is redundant on tap devices. */
    .sel-hint {
      display: none;
    }
  }
</style>
