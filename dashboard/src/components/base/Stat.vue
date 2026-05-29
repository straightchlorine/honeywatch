<script setup lang="ts">
  import { computed } from 'vue'

  type Trend = 'up' | 'down' | 'neutral'

  /**
   * Trend is caller-supplied semantics, not derived from delta. The caller decides
   * whether an upward delta is "good" (up) or "bad" (down) for the metric.
   */
  const props = defineProps<{
    value: number | string
    label: string
    trend?: Trend
    delta?: string
  }>()

  const deltaClass = computed(() => {
    if (!props.trend) return ''
    return `trend-${props.trend}`
  })

  // Non-color cues so trend direction is not conveyed by color alone (WCAG 1.4.1).
  const trendSymbol = computed(() =>
    props.trend === 'up' ? '▲' : props.trend === 'down' ? '▼' : '',
  )
  const trendWord = computed(() =>
    props.trend === 'up' ? 'increase' : props.trend === 'down' ? 'decrease' : '',
  )
</script>

<template>
  <div class="stat">
    <div class="stat-line">
      <span class="stat-value">{{ value }}</span>
      <span v-if="delta" class="stat-delta" :class="deltaClass">
        <span v-if="trendSymbol" class="stat-trend-symbol" aria-hidden="true">{{
          trendSymbol
        }}</span>
        <span v-if="trendWord" class="visually-hidden">{{ trendWord }}: </span>{{ delta }}
      </span>
    </div>
    <span class="stat-label">{{ label }}</span>
  </div>
</template>

<style scoped>
  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-line {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .stat-value {
    font-size: 36px;
    line-height: 1;
    font-weight: 700;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
  }

  .stat-label {
    color: var(--text-muted);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 500;
  }

  .stat-delta {
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .stat-trend-symbol {
    margin-right: 2px;
  }

  .trend-up {
    color: var(--success);
  }

  .trend-down {
    color: var(--error);
  }

  .trend-neutral {
    color: var(--text-muted);
  }
</style>
