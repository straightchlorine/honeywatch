<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";

type Bucket = "hour" | "day" | "month";

interface ActivityPoint {
  bucket: string;
  count: number;
}

const LIMITS: Record<Bucket, number> = { hour: 24, day: 30, month: 12 };

const bucket = ref<Bucket>("day");
const raw = ref<ActivityPoint[]>([]);
const loading = ref(false);

async function fetchData() {
  loading.value = true;
  try {
    const r = await fetch(`/api/stats/activity?bucket=${bucket.value}`);
    if (r.ok) raw.value = await r.json();
  } finally {
    loading.value = false;
  }
}

onMounted(fetchData);
watch(bucket, fetchData);

const data = computed(() => raw.value.slice(-LIMITS[bucket.value]));
const max = computed(() => Math.max(...data.value.map((d) => d.count), 1));
const mid = computed(() => Math.round(max.value / 2));

const labelStep = computed(() => {
  if (bucket.value === "hour") return 4;
  if (bucket.value === "day") return 5;
  return 1;
});

function fmtTooltip(iso: string): string {
  const d = new Date(iso);
  if (bucket.value === "month")
    return d.toLocaleDateString("en", { year: "numeric", month: "short", timeZone: "UTC" });
  if (bucket.value === "day")
    return d.toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" });
  return d.toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", hour12: false, timeZone: "UTC" });
}

function fmtXLabel(iso: string): string {
  const d = new Date(iso);
  if (bucket.value === "month")
    return d.toLocaleDateString("en", { month: "short", timeZone: "UTC" });
  if (bucket.value === "day")
    return d.toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" });
  return d.toLocaleString("en", { hour: "2-digit", hour12: false, timeZone: "UTC" });
}
</script>

<template>
  <div class="panel">
    <div class="panel-header">
      <h2 class="panel-title">Attack Activity</h2>
      <div class="tabs">
        <button
          v-for="b in (['hour', 'day', 'month'] as const)"
          :key="b"
          :class="['tab', { active: bucket === b }]"
          @click="bucket = b"
        >
          {{ b === 'hour' ? 'Hour (last 24h)' : b === 'day' ? 'Day (last 30)' : 'Month (last 12)' }}
        </button>
      </div>
    </div>

    <p v-if="loading" class="placeholder">Loading…</p>
    <p v-else-if="data.length === 0" class="placeholder">No data</p>

    <div v-else class="chart-outer">
      <!-- bars + y-axis -->
      <div class="chart-with-y">
        <div class="y-axis">
          <span>{{ max.toLocaleString() }}</span>
          <span>{{ mid.toLocaleString() }}</span>
          <span>0</span>
        </div>
        <div class="chart-bars-wrap">
          <div class="gridline" style="top: 0%"></div>
          <div class="gridline" style="top: 50%"></div>
          <div class="gridline" style="top: 100%"></div>
          <div class="bars-inner">
            <div
              v-for="item in data"
              :key="item.bucket"
              class="vbar-col"
              :title="`${fmtTooltip(item.bucket)}: ${item.count.toLocaleString()}`"
            >
              <div
                class="vbar-fill"
                :style="{ height: (item.count / max) * 100 + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- x-axis labels -->
      <div class="x-axis">
        <div class="y-spacer"></div>
        <div class="x-labels">
          <template v-for="(item, i) in data" :key="item.bucket">
            <span
              v-if="i % labelStep === 0"
              class="x-lbl"
              :style="{ left: (i / (data.length - 1)) * 100 + '%' }"
            >{{ fmtXLabel(item.bucket) }}</span>
          </template>
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
  margin-bottom: 1.25rem;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.panel-title {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.tabs {
  display: flex;
  gap: 0.35rem;
}

.tab {
  background: none;
  border: 1px solid #1f242b;
  color: var(--muted);
  font-size: 0.72rem;
  font-family: inherit;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.tab.active {
  border-color: var(--accent);
  color: var(--accent);
}

.tab:hover:not(.active) {
  color: var(--fg);
  border-color: #2e3640;
}

.placeholder {
  color: var(--muted);
  font-size: 0.85rem;
  padding: 2rem 0;
  text-align: center;
}

.chart-outer {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chart-with-y {
  display: flex;
  gap: 6px;
  height: 10rem;
}

.y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  width: 3rem;
  font-size: 0.65rem;
  color: var(--muted);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  padding-bottom: 1px;
}

.chart-bars-wrap {
  position: relative;
  flex: 1;
}

.gridline {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px solid #1f242b;
  pointer-events: none;
}

.bars-inner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: flex-end;
  gap: 2px;
}

.vbar-col {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  cursor: default;
}

.vbar-fill {
  width: 100%;
  background: var(--accent);
  border-radius: 2px 2px 0 0;
  opacity: 0.85;
  transition: height 0.3s ease;
  min-height: 1px;
}

.x-axis {
  display: flex;
  gap: 6px;
}

.y-spacer {
  width: 3rem;
  flex-shrink: 0;
}

.x-labels {
  flex: 1;
  position: relative;
  height: 1.2rem;
}

.x-lbl {
  position: absolute;
  transform: translateX(-50%);
  font-size: 0.6rem;
  color: var(--muted);
  white-space: nowrap;
}
</style>
