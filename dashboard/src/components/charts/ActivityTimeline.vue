<script setup lang="ts">
import { computed } from 'vue'
import type { ActivityBucketResponse } from '@/api/generated/types.gen'
import { fmtNumber } from '@/utils/format'
import EmptyState from '@/components/base/EmptyState.vue'

const props = defineProps<{ buckets: ActivityBucketResponse[]; label: string }>()

const max = computed(() => props.buckets.reduce((m, b) => Math.max(m, b.count), 0))

const bars = computed(() =>
  props.buckets.map((b, i) => ({
    key: `${b.bucket}-${i}`,
    // 2% floor so any non-zero day stays visible against the baseline.
    heightPct: max.value > 0 ? `${Math.max(2, Math.round((b.count / max.value) * 100))}%` : '0%',
    label: fmtDate(b.bucket),
    title: `${fmtDate(b.bucket)} — ${fmtNumber(b.count)} sessions`,
  })),
)

// Sparse x-axis: first / middle / last only, so 30 labels don't crowd.
const labelIdx = computed(() => {
  const n = props.buckets.length
  if (n === 0) return new Set<number>()
  return new Set([0, Math.floor((n - 1) / 2), n - 1])
})

const ariaLabel = computed(() => {
  if (!props.buckets.length) return `${props.label}. No sessions recorded yet.`
  let peak = props.buckets[0]!
  for (const b of props.buckets) if (b.count > peak.count) peak = b
  return (
    `${props.label} over ${props.buckets.length} days. ` +
    `Peak ${fmtDate(peak.bucket)} with ${fmtNumber(peak.count)} sessions.`
  )
})

function fmtDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}
</script>

<template>
  <EmptyState v-if="!buckets.length" title="No activity yet" />
  <figure v-else class="timeline" role="img" :aria-label="ariaLabel">
    <div class="y-tick" aria-hidden="true">{{ fmtNumber(max) }}</div>
    <div class="bars" aria-hidden="true">
      <div v-for="bar in bars" :key="bar.key" class="bar-col" :title="bar.title">
        <span class="bar" :style="{ height: bar.heightPct }" />
      </div>
    </div>
    <div class="x-axis" aria-hidden="true">
      <span v-for="(bar, i) in bars" :key="`x-${bar.key}`" class="x-label">
        {{ labelIdx.has(i) ? bar.label : '' }}
      </span>
    </div>
    <ul class="visually-hidden">
      <li v-for="bar in bars" :key="`sr-${bar.key}`">{{ bar.title }}</li>
    </ul>
  </figure>
</template>

<style scoped>
.timeline {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  height: 116px;
}

.y-tick {
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  color: var(--text-dim);
  font-family: var(--font-mono);
}

.bars {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  align-items: flex-end;
  gap: 2px;
}

.bar-col {
  flex: 1 1 0;
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.bar {
  width: 100%;
  background: var(--accent);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  transition: height var(--motion-base) ease;
}

.bar-col:hover .bar {
  background: var(--accent-strong);
}

.x-axis {
  display: flex;
  gap: 2px;
}

.x-label {
  flex: 1 1 0;
  text-align: center;
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  color: var(--text-dim);
  overflow: hidden;
  white-space: nowrap;
}
</style>
