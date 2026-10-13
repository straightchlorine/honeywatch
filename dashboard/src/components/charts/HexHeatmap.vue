<script setup lang="ts">
  import { computed, onScopeDispose, ref } from 'vue'
  import type { HeatmapPointResponse } from '@/api/generated/types.gen'
  import { buildHeatmapGrid, WEEKDAY_LABELS } from '@/utils/heatmapGrid'
  import { busiestHour, busiestWeekday } from '@/utils/activityKpis'
  import { fmtNumber, fmtCompact } from '@/utils/format'
  import { hexPoints } from '@/utils/hex'
  import { seq } from '@/composables/useSeqScale'
  import { useHwTooltip, type TooltipRow } from '@/composables/useHwTooltip'
  import { useRovingGrid } from '@/composables/useRovingGrid'
  import { useReducedMotion } from '@/composables/useReducedMotion'
  import EmptyState from '@/components/base/EmptyState.vue'
  import HexFocusRing from '@/components/base/HexFocusRing.vue'
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
  // Gutter holds the 3-letter weekday labels (12px on screen); compact has fewer, bigger units per px.
  const GUT = computed(() => (compact.value ? 26 : 22))
  const VW = computed(() => GUT.value + HXW * (cols.value + 0.5) + 8)

  // The svg scales with its viewBox, so labels are sized in units as px / scale
  // to stay 12px on every viewport. Scale needs the width only (height is auto),
  // so VH may depend on it without a loop. 1 until measured (first paint, jsdom).
  const LABEL_PX = 12
  const svgW = ref(0)
  const fs = computed(() => LABEL_PX / (svgW.value > 0 ? svgW.value / VW.value : 1))
  let ro: ResizeObserver | null = null
  let observed: unknown = null
  // The svg only exists once there is data, so the function ref (re)attaches whenever it appears.
  function observe(el: unknown): void {
    if (el === observed) return
    observed = el
    ro?.disconnect()
    ro = null
    if (!el) return
    ro = new ResizeObserver(([e]) => {
      svgW.value = e?.contentRect.width ?? 0
    })
    ro.observe(el as Element)
  }

  // The hour axis sits in a band under the last hex row, sized in label units
  // so it is one line of text plus a ~5px gap at any scale.
  const HEX_BOTTOM = TOP + 1.5 * R * 6 + 2 * R
  const axisY = computed(() => HEX_BOTTOM + fs.value * 1.15)
  const VH = computed(() => axisY.value + fs.value * 0.1)

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
    const norm =
      hi === loV ? 1 : (Math.log1p(n) - Math.log1p(loV)) / (Math.log1p(hi) - Math.log1p(loV))
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

  // Hour axis under the comb: 00/06/12/18 at the matching column (bin start).
  // Last row (Sat) is even, so it has no half-hex shift.
  const axisTicks = computed(() =>
    [0, 6, 12, 18].map((hr) => {
      const h = hr / hoursPerCell.value
      return {
        hr,
        label: String(hr).padStart(2, '0'),
        x: GUT.value + HXW * h + HXW / 2,
      }
    }),
  )

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
      `with ${fmtNumber(bh.count)} sessions. Busiest times are listed below the chart.`
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

  function tip(c: Cell): [string, TooltipRow[]] {
    const pct = weeklyMean.value > 0 ? Math.round((c.n / weeklyMean.value) * 100 - 100) : 0
    return [
      cellTitle(c),
      [
        ['Sessions', fmtNumber(c.n)],
        ['vs weekly average', `${pct > 0 ? '+' : ''}${pct}%`],
      ],
    ]
  }

  // Rows are staggered by half a hex, so Up/Down keep the column index (one of the two nearest).
  const { tabKey, ring, onFocus, onBlur, onKeydown } = useRovingGrid({
    cells,
    cols,
    home: () => hottestCell.value?.key,
    geom: (c) => ({ cx: c.cx, cy: c.cy, r: R - 0.9 }),
    tip,
  })

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
          :ref="observe"
          class="hex-svg"
          role="graphics-document"
          :aria-label="ariaLabel"
          :viewBox="`0 0 ${VW} ${VH}`"
        >
          <text
            v-for="w in 7"
            :key="`d-${w - 1}`"
            :x="GUT - fs * 0.5"
            :y="TOP + R + 1.5 * R * (w - 1) + fs * 0.36"
            text-anchor="end"
            fill="var(--text-dim)"
            :font-size="fs"
            font-family="var(--font-mono)"
          >
            {{ WEEKDAY_LABELS[w - 1] }}
          </text>
          <text
            v-for="t in axisTicks"
            :key="`h-${t.hr}`"
            :x="t.x"
            :y="axisY"
            text-anchor="middle"
            fill="var(--text-dim)"
            :font-size="fs"
            font-family="var(--font-mono)"
            aria-hidden="true"
          >
            {{ t.label }}
          </text>
          <polygon
            v-for="c in cells"
            :key="c.key"
            class="hexcell"
            :points="hexPoints(c.cx, c.cy, R - 0.9)"
            :fill="c.fill"
            :style="{ animationDelay: cellDelay(c) }"
            :tabindex="c.key === tabKey ? 0 : -1"
            role="button"
            :aria-label="`${cellTitle(c)}: ${fmtNumber(c.n)} sessions`"
            @pointerenter="tt.show(...tip(c), undefined, $event)"
            @pointermove="tt.move($event)"
            @pointerleave="tt.hide()"
            @focus="onFocus(c, $event)"
            @blur="onBlur"
            @keydown="onKeydown(c, $event)"
          />
          <polygon
            v-if="hottestCell"
            class="hex-crown"
            :points="hexPoints(hottestCell.cx, hottestCell.cy, R + 0.6)"
            fill="none"
            stroke="var(--seq-7)"
            stroke-width="1.3"
          />
          <HexFocusRing v-if="ring" v-bind="ring" />
        </svg>
      </div>

      <footer class="hex-footer">
        <div class="hex-footer-left">
          <h3 id="hot-cells-title" class="hex-footer-title">
            Busiest times<span class="hex-footer-grain">{{
              compact ? '3-hour bands' : 'by hour'
            }}</span>
          </h3>
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
        <SeqLegend class="hex-legend" title="Sessions" :min="legendMin" :max="legendMax" />
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
    overflow: visible;
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
    padding: 10px 0;
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

  .hex-footer-grain {
    margin-left: 8px;
    font-weight: 500;
    letter-spacing: normal;
    text-transform: none;
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
      padding: 12px 0 0;
      min-height: auto;
    }

    .hex-footer-left {
      width: 100%;
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
    }

    .hex-footer,
    .hex-legend {
      min-width: 0;
    }

    .hot-list {
      display: grid;
      grid-template-columns: auto 1fr auto;
      column-gap: 9px;
      row-gap: 6px;
    }

    .hot-row {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: subgrid;
    }

    .hot-row + .hot-row {
      border-top: 1px dotted var(--grid-line);
      padding-top: 8px;
    }

    .hot-value {
      text-align: right;
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
