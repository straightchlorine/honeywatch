<script setup lang="ts">
import { computed } from 'vue'
import type { HeatmapPointResponse } from '@/api/generated/types.gen'
import { fmtNumber } from '@/utils/format'
import { buildHeatmapGrid, WEEKDAY_LABELS } from '@/utils/heatmapGrid'
import { busiestHour, busiestWeekday } from '@/utils/activityKpis'
import { useHeatScale } from './useHeatScale'
import WorldMapLegend from '@/components/map/WorldMapLegend.vue'

const props = defineProps<{ points: HeatmapPointResponse[] }>()

const HOURS = Array.from({ length: 24 }, (_, h) => h)
const HOUR_LABEL_AT = new Set([0, 6, 12, 18])

const built = computed(() => buildHeatmapGrid(props.points))
const scale = computed(() => useHeatScale(props.points.map((p) => p.count), { zeroColor: 'var(--bg-2)' }))

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
    <div class="grid" aria-hidden="true">
      <span class="corner" />
      <span v-for="h in HOURS" :key="`h-${h}`" class="hour-label">
        {{ HOUR_LABEL_AT.has(h) ? String(h).padStart(2, '0') : '' }}
      </span>

      <template v-for="(row, w) in built.grid" :key="`w-${w}`">
        <span class="day-label">{{ WEEKDAY_LABELS[w] }}</span>
        <span
          v-for="(n, h) in row"
          :key="`c-${w}-${h}`"
          class="cell"
          :style="{ background: scale.fill(n) }"
          :title="cellTitle(w, h, n)"
        />
      </template>
    </div>

    <WorldMapLegend
      :max="scale.max"
      :ramp="scale.rampStops"
      zero-color="var(--bg-2)"
      zero-label="no sessions"
    />

    <ul class="visually-hidden">
      <li v-for="c in populated" :key="c.key">{{ c.text }}</li>
    </ul>
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
  .grid {
    /* Below md the 24 columns can't stay legible at 1fr; let the grid scroll. */
    min-width: 560px;
  }
  .heatmap {
    overflow-x: auto;
  }
}
</style>
