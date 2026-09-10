<script setup lang="ts">
  import { computed, onScopeDispose, ref } from 'vue'
  import type { HeatmapPointResponse } from '@/api/generated/types.gen'
  import { buildHeatmapGrid, WEEKDAY_LABELS } from '@/utils/heatmapGrid'
  import { busiestHour, busiestWeekday } from '@/utils/activityKpis'
  import { fmtNumber, fmtCompact } from '@/utils/format'
  import { hexPoints } from '@/utils/hex'
  import { seq } from '@/composables/useSeqScale'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { useReducedMotion } from '@/composables/useReducedMotion'
  import EmptyState from '@/components/base/EmptyState.vue'
  import SeqLegend from '@/components/base/SeqLegend.vue'

  const { points } = defineProps<{ points: HeatmapPointResponse[] }>()

  const tt = useHwTooltip()
  const reduced = useReducedMotion()

  // Below 900px, bin hours 3-wide to meet WCAG 2.5.8 touch target size on phones.
  const compactMql =
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(max-width: 900px)')
      : null
  const compact = ref(compactMql?.matches ?? false)

  function onCompactChange(e: MediaQueryListEvent): void {
    compact.value = e.matches
  }

  compactMql?.addEventListener('change', onCompactChange)
  // Tests call this outside a component scope; silence disposal failure.
  onScopeDispose(() => compactMql?.removeEventListener('change', onCompactChange), true)

  // Pointy-top hex layout; fixed ViewBox + uniform SVG scaling preserves x-spacing and prevents sparse appearance.
  const R = 12
  const HXW = Math.sqrt(3) * R
  const TOP = 6
  const hoursPerCell = computed(() => (compact.value ? 3 : 1))
  const cols = computed(() => 24 / hoursPerCell.value)
  // Gutter scales with column count to preserve label readability on narrow viewports.
  const GUT = computed(() => (compact.value ? 32 : 46))
  const VW = computed(() => GUT.value + HXW * (cols.value + 0.5) + 8)
  const VH = TOP + 1.5 * R * 6 + 2 * R + 6

  const built = computed(() => buildHeatmapGrid(points))
  const isEmpty = computed(() => built.value.max === 0)

  // Ensures all consumers (color ramp, legend, footer, SR list) read the same binned grid so they never disagree on cell meaning.
  const binnedGrid = computed(() => {
    const { grid } = built.value
    const hpc = hoursPerCell.value
    const nCols = cols.value
    const out: number[][] = []
    for (let w = 0; w < 7; w++) {
      const row: number[] = []
      for (let h = 0; h < nCols; h++) {
        let n = 0
        for (let i = 0; i < hpc; i++) n += grid[w]![h * hpc + i]!
        row.push(n)
      }
      out.push(row)
    }
    return out
  })
  // Binned grid max (not hourly), since ramp and legend both key off it.
  const max = computed(() =>
    binnedGrid.value.reduce((m, row) => row.reduce((mm, n) => Math.max(mm, n), m), 0),
  )
  // Smallest positive count; color ramp uses [lo, hi] to span the occupied range, not [0, hi].
  const lo = computed(() => {
    let m = Infinity
    for (const row of binnedGrid.value) {
      for (const n of row) if (n > 0 && n < m) m = n
    }
    return m === Infinity ? 0 : m
  })
  const weeklyMean = computed(() => {
    const total = binnedGrid.value.reduce((a, row) => a + row.reduce((b, n) => b + n, 0), 0)
    return total / (7 * cols.value)
  })

  interface Cell {
    key: string
    weekday: number
    hour: number
    n: number
    cx: number
    cy: number
    fill: string
  }

  // Log-normalize [lo, hi] and floor at 0.08 to span the full ramp while keeping populated cells distinct from empty.
  function cellFill(n: number): string {
    if (n <= 0) return 'var(--surface-2)'
    const hi = max.value
    const loV = lo.value
    const norm = hi === loV ? 1 : (Math.log1p(n) - Math.log1p(loV)) / (Math.log1p(hi) - Math.log1p(loV))
    return seq(0.08 + 0.92 * norm)
  }

  const cells = computed<Cell[]>(() => {
    const grid = binnedGrid.value
    const gut = GUT.value
    const hpc = hoursPerCell.value
    const nCols = cols.value
    const out: Cell[] = []
    for (let w = 0; w < 7; w++) {
      const cy = TOP + R + 1.5 * R * w
      for (let h = 0; h < nCols; h++) {
        const n = grid[w]![h]!
        const cx = gut + HXW * h + HXW / 2 + (w % 2 ? HXW / 2 : 0)
        out.push({ key: `${w}-${h}`, weekday: w, hour: h * hpc, n, cx, cy, fill: cellFill(n) })
      }
    }
    return out
  })

  const hottestCell = computed<Cell | null>(() => {
    let best: Cell | null = null
    for (const c of cells.value) if (!best || c.n > best.n) best = c
    return best && best.n > 0 ? best : null
  })

  const hotCells = computed(() =>
    [...cells.value]
      .filter((c) => c.n > 0)
      .sort((a, b) => b.n - a.n)
      .slice(0, 5)
      .map((c) => ({
        key: c.key,
        fill: c.fill,
        label: compact.value ? cellTitle(c) : cellShortTitle(c),
        valueLabel: fmtNumber(c.n),
      })),
  )

  const legendMax = computed(() => fmtCompact(max.value))
  const legendMin = computed(() => fmtCompact(lo.value))

  // Offscreen SR list: only the populated cells (not all the zero ones).
  const populated = computed(() =>
    cells.value
      .filter((c) => c.n > 0)
      .map((c) => ({
        key: c.key,
        text: `${cellTitle(c)} UTC: ${fmtNumber(c.n)} sessions`,
      })),
  )

  const ariaLabel = computed(() => {
    const bh = busiestHour(points)
    const bd = busiestWeekday(points)
    if (bh.count <= 0) return 'Sessions by hour and weekday. No sessions recorded yet.'
    return (
      `Sessions by hour and weekday, UTC. Busiest: ${bd.value} at ${bh.value} ` +
      `with ${fmtNumber(bh.count)} sessions. Busiest times are listed beside the chart.`
    )
  })

  /** Weekday and start hour only; full range in cellTitle(). */
  function cellShortTitle(c: Cell): string {
    return `${WEEKDAY_LABELS[c.weekday]} ${String(c.hour).padStart(2, '0')}:00`
  }

  function cellTitle(c: Cell): string {
    const end = c.hour + hoursPerCell.value - 1
    return `${WEEKDAY_LABELS[c.weekday]} ${String(c.hour).padStart(2, '0')}:00-${String(end).padStart(2, '0')}:59`
  }

  function showTooltip(c: Cell, e: { clientX?: number; clientY?: number }): void {
    const pct = weeklyMean.value > 0 ? Math.round((c.n / weeklyMean.value) * 100 - 100) : 0
    tt.show(cellTitle(c), [
      ['Sessions', fmtNumber(c.n)],
      ['vs weekly average', `${pct > 0 ? '+' : ''}${pct}%`],
    ])
    if (e.clientX !== undefined && e.clientY !== undefined) {
      tt.move({ clientX: e.clientX, clientY: e.clientY })
    }
  }

  function cellDelay(c: Cell): string {
    return reduced.value ? '0ms' : `${c.hour * 14 + c.weekday * 6}ms`
  }
</script>

<template>
  <figure class="hex-heatmap">
    <EmptyState
      v-if="isEmpty"
      title="No sessions yet"
      hint="This fills in as the honeypot records sessions."
    />
    <template v-else>
      <div class="hex-chart">
        <!-- graphics-document role allows interactive cells; img/aria-hidden would violate nested-interactive/aria-hidden-focus. -->
        <svg
          class="hex-svg"
          role="graphics-document"
          :aria-label="ariaLabel"
          :viewBox="`0 0 ${VW} ${VH}`"
        >
          <text
            v-for="w in 7"
            :key="`d-${w - 1}`"
            :x="GUT - 10"
            :y="TOP + R + 1.5 * R * (w - 1) + 3"
            text-anchor="end"
            fill="var(--text-dim)"
            font-size="8.5"
            font-family="var(--font-mono)"
          >
            {{ WEEKDAY_LABELS[w - 1] }}
          </text>
          <polygon
            v-for="c in cells"
            :key="c.key"
            class="hexcell"
            :points="hexPoints(c.cx, c.cy, R - 0.9)"
            :fill="c.fill"
            :style="{ animationDelay: cellDelay(c) }"
            tabindex="0"
            role="button"
            :aria-label="`${cellTitle(c)}: ${fmtNumber(c.n)} sessions`"
            @pointerenter="showTooltip(c, $event)"
            @pointermove="tt.move($event)"
            @pointerleave="tt.hide()"
            @focus="showTooltip(c, {})"
            @blur="tt.hide()"
            @keydown.enter.space.prevent="showTooltip(c, {})"
          />
          <polygon
            v-if="hottestCell"
            class="hex-crown"
            :points="hexPoints(hottestCell.cx, hottestCell.cy, R + 0.6)"
            fill="none"
            stroke="var(--seq-7)"
            stroke-width="1.3"
          />
        </svg>
      </div>

      <footer class="hex-footer">
        <div class="hex-footer-left">
          <h3 id="hot-cells-title" class="hex-footer-title">Busiest times</h3>
          <!-- Named from heading to avoid SR reading the same info twice (name + each item). -->
          <ul class="hot-list" aria-labelledby="hot-cells-title">
            <li v-for="c in hotCells" :key="c.key" class="hot-row">
              <svg class="hot-swatch" width="14" height="15" viewBox="0 0 14 15" aria-hidden="true">
                <polygon :points="hexPoints(7, 7.5, 6)" :fill="c.fill" />
              </svg>
              <span class="hot-label">{{ c.label }}</span>
              <b class="hot-value">{{ c.valueLabel }}</b>
            </li>
          </ul>
        </div>
        <SeqLegend class="hex-legend" :min="legendMin" :max="legendMax" />
      </footer>

      <ul class="visually-hidden">
        <li v-for="c in populated" :key="c.key">{{ c.text }}</li>
      </ul>
    </template>
  </figure>
</template>

<style scoped>
  .hex-heatmap {
    margin: 0;
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .hex-chart {
    flex: 1 1 auto;
    min-width: 0;
    display: block;
  }

  .hex-chart svg {
    width: 100%;
    height: auto;
  }

  .hexcell {
    transition: filter var(--motion-fast);
    cursor: pointer;
    animation: hex-in 300ms ease-out both;
  }

  .hexcell:hover {
    filter: brightness(1.45);
  }

  .hexcell:focus {
    outline: none;
  }

  .hexcell:focus-visible {
    stroke: var(--accent-hot);
    stroke-width: 2;
  }

  @keyframes hex-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .hex-footer {
    flex: none;
    display: flex;
    align-items: center;
    gap: 16px;
    border-top: 1px solid var(--grid-line);
    padding-top: 10px;
    margin-top: 10px;
    min-height: 26px;
  }

  .hex-footer-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .hex-footer-title {
    margin: 0;
    font: 650 11px var(--font-sans);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    flex: none;
    white-space: nowrap;
  }

  .hot-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: 14px;
    flex-wrap: nowrap;
    overflow: hidden;
    min-width: 0;
  }

  .hot-row {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 12.5px;
    color: var(--text-muted);
  }

  .hot-swatch {
    flex: none;
  }

  .hot-label {
    white-space: nowrap;
  }

  .hot-value {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    color: var(--text);
    font-weight: 600;
  }

  .hex-legend {
    margin-left: auto;
  }

  @media (max-width: 900px) {
    .hex-footer {
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
      padding-top: 12px;
      min-height: auto;
    }

    .hex-footer-left {
      width: 100%;
      flex-wrap: wrap;
    }

    .hex-legend {
      margin-left: 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .hexcell {
      animation: none;
    }
  }
</style>
