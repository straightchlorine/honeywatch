<script setup lang="ts">
  import { computed } from 'vue'
  import type { HeatmapPointResponse } from '@/api/generated/types.gen'
  import { fmtNumber } from '@/utils/format'
  import { buildHeatmapGrid, WEEKDAY_LABELS } from '@/utils/heatmapGrid'
  import { busiestHour, busiestWeekday } from '@/utils/activityKpis'
  import { useHeatScale } from './useHeatScale'
  import WorldMapLegend from '@/components/map/WorldMapLegend.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import Tooltip from '@/components/base/Tooltip.vue'
  import { useTooltip } from '@/components/base/useTooltip'

  const props = defineProps<{ points: HeatmapPointResponse[] }>()

  // Themed tooltip replacing the native title= hover on each cell.
  const tt = useTooltip()

  const HOURS = Array.from({ length: 24 }, (_, h) => h)
  const HOUR_LABEL_AT = new Set([0, 6, 12, 18])

  const built = computed(() => buildHeatmapGrid(props.points))
  const scale = computed(() =>
    useHeatScale(
      props.points.map((p) => p.count),
      { zeroColor: 'var(--bg-2)' },
    ),
  )
  const isEmpty = computed(() => scale.value.max === 0)

  const ariaLabel = computed(() => {
    const bh = busiestHour(props.points)
    const bd = busiestWeekday(props.points)
    if (bh.count <= 0) return 'Attack heatmap by hour and weekday (UTC). No sessions recorded yet.'
    return (
      `Attack heatmap by hour and weekday (UTC). Busiest: ${bd.value} at ${bh.value} UTC ` +
      `with ${fmtNumber(bh.count)} sessions.`
    )
  })

  // Offscreen SR list: only the populated cells (not all 168 zeros).
  const populated = computed(() => {
    const rows: { key: string; text: string }[] = []
    const { grid } = built.value
    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 24; h++) {
        const n = grid[w]![h]!
        if (n > 0) {
          rows.push({
            key: `${w}-${h}`,
            text: `${WEEKDAY_LABELS[w]} ${String(h).padStart(2, '0')}:00 UTC: ${fmtNumber(n)} sessions`,
          })
        }
      }
    }
    return rows
  })

  function cellTitle(w: number, h: number, n: number): string {
    return `${WEEKDAY_LABELS[w]} ${String(h).padStart(2, '0')}:00 UTC — ${fmtNumber(n)} sessions`
  }
</script>

<template>
  <figure class="heatmap" role="img" :aria-label="ariaLabel">
    <EmptyState
      v-if="isEmpty"
      class="heat-empty"
      title="No sessions yet"
      hint="The heatmap fills in as the honeypot records activity."
    />
    <template v-else>
      <!-- Only the grid scrolls horizontally on mobile; the legend below must
           stay put, so it lives outside this scroll container. -->
      <div class="grid-scroll">
        <div class="grid" aria-hidden="true">
          <span class="corner" />
          <span v-for="h in HOURS" :key="`h-${h}`" class="hour-label">
            {{ HOUR_LABEL_AT.has(h) ? String(h).padStart(2, '0') : '' }}
          </span>

          <template v-for="(row, w) in built.grid" :key="`w-${w}`">
            <span class="day-label">{{ WEEKDAY_LABELS[w] }}</span>
            <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
            <span
              v-for="(n, h) in row"
              :key="`c-${w}-${h}`"
              class="cell"
              :style="{ background: scale.fill(n) }"
              @mouseenter="tt.show(cellTitle(w, h, n), $event)"
              @mousemove="tt.show(cellTitle(w, h, n), $event)"
              @mouseleave="tt.hide()"
            />
            <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
          </template>
        </div>
      </div>

      <WorldMapLegend
        :max="scale.max"
        :ramp="scale.rampStops"
        zero-color="var(--bg-2)"
        zero-label="no sessions"
      />
    </template>

    <ul class="visually-hidden">
      <li v-for="c in populated" :key="c.key">{{ c.text }}</li>
    </ul>
    <Tooltip v-bind="tt.state" />
  </figure>
</template>

<style scoped>
  .heatmap {
    margin: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .grid-scroll {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .heat-empty {
    flex: 1 1 auto;
    min-height: 0;
  }

  .grid {
    flex: 1 1 auto;
    min-height: 0;
    display: grid;
    grid-template-columns: auto repeat(24, minmax(0, 1fr));
    grid-template-rows: auto repeat(7, minmax(14px, 1fr));
    gap: 2px;
  }

  .corner {
    grid-column: 1;
  }

  .hour-label,
  .day-label {
    font-size: var(--type-xs);
    line-height: 1;
    color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }

  .hour-label {
    align-self: end;
    text-align: center;
  }

  .day-label {
    align-self: center;
    padding-right: var(--space-2);
  }

  .cell {
    border-radius: 2px;
    transition: background var(--motion-base) ease;
  }

  @media (max-width: 768px) {
    /* Fit the 24 columns to the viewport instead of forcing a 560px horizontal
     scroll (the scrollbar read as a stray grey bar under the grid, and the page
     scrolled sideways). Cells are colour blocks, so they stay legible when small;
     the offscreen list + per-cell titles carry the exact values. */
    .grid {
      gap: 1px;
    }
  }
</style>
