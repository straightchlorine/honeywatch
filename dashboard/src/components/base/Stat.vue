<script setup lang="ts">
  import { computed } from 'vue'

  type Trend = 'up' | 'down' | 'neutral'

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
</script>

<template>
  <div class="stat">
    <div class="stat-line">
      <span class="stat-value">{{ value }}</span>
      <span v-if="delta" class="stat-delta" :class="deltaClass">{{ delta }}</span>
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
