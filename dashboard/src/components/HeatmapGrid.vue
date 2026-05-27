<script setup lang="ts">
import { computed } from "vue";

interface HeatmapPoint {
  hour: number;
  weekday: number;
  count: number;
}

const props = defineProps<{ data: HeatmapPoint[] }>();

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

const maxCount = computed(() =>
  Math.max(...props.data.map((d) => d.count), 1)
);

const grid = computed(() => {
  const map = new Map<string, number>();
  for (const p of props.data) map.set(`${p.weekday}-${p.hour}`, p.count);
  return DAYS.map((day, dow) => ({
    day,
    hours: HOURS.map((h) => ({ hour: h, count: map.get(`${dow}-${h}`) ?? 0 })),
  }));
});

function heatColor(count: number): string {
  if (count === 0) return "#1a1f27";
  const t = count / maxCount.value;
  const r = Math.round(40 + t * (125 - 40));
  const g = Math.round(80 + t * (211 - 80));
  const b = Math.round(120 + t * (252 - 120));
  return `rgb(${r},${g},${b})`;
}
</script>

<template>
  <div class="panel">
    <h2 class="panel-title">Attack Heatmap <span class="sub">hour × weekday</span></h2>
    <div class="hm-wrap">
      <div v-for="row in grid" :key="row.day" class="hm-row">
        <span class="hm-day">{{ row.day }}</span>
        <div class="hm-cells">
          <div
            v-for="cell in row.hours"
            :key="cell.hour"
            class="hm-cell"
            role="img"
            :style="{ background: heatColor(cell.count) }"
            :aria-label="`${row.day} ${String(cell.hour).padStart(2, '0')}:00 — ${cell.count} sessions`"
            :title="`${row.day} ${String(cell.hour).padStart(2, '0')}:00 — ${cell.count} sessions`"
          />
        </div>
      </div>
      <div class="hm-row hm-axis">
        <span class="hm-day"></span>
        <div class="hm-cells">
          <span
            v-for="h in HOURS"
            :key="h"
            class="hm-cell hm-hl"
          >{{ h % 6 === 0 ? h : "" }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  background: #101419;
  border: 1px solid #1f242b;
  border-radius: 0.75rem;
  padding: 1.25rem 1.5rem;
}

.panel-title {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin-bottom: 1rem;
}

.sub {
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
}

.hm-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hm-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hm-day {
  width: 2.5rem;
  font-size: 0.72rem;
  color: var(--muted);
  text-align: right;
  flex-shrink: 0;
}

.hm-cells {
  display: grid;
  grid-template-columns: repeat(24, 1fr);
  gap: 2px;
  flex: 1;
}

.hm-cell {
  aspect-ratio: 1;
  border-radius: 2px;
}

.hm-axis .hm-cells {
  gap: 2px;
}

.hm-hl {
  font-size: 0.6rem;
  color: var(--muted);
  text-align: center;
  background: none !important;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
